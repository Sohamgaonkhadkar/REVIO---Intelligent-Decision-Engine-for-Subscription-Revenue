"""SIM world model — reimplemented from the documented Phase 3A mechanics
(D-009). NOT recoverysim v0.3; parameters come from the DATASET_BUILD_REPORT
where stated and from the assumption registry otherwise.

Mechanics (Phase 3A §5/§8):
  retry success = mandate_active × bank_operational × balance_sufficient × jitter
  contact response = base_hazard(intent) × channel_effect × fatigue_mult × urgency
Post-decision draws happen via keyed RNG only (probabilities first, outcomes
after — the journal carries outcomes, never the latent state).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sim.rng import bernoulli, stream

# ---- registered parameter bands (assumption_registry sources) ---------------
BANK_OUTAGE_RATE_PER_DAY = 0.10      # DATA_DERIVED: Poisson(0.10)/day
BANK_OUTAGE_MEAN_H = 1.5             # DATA_DERIVED: ~1.5h mean
JITTER_SUCCESS = 0.97                # residual issuer noise band 0.95–0.99

INTENT_BASE_HAZARD = {               # ASSUMED (Phase 3A §5 archetype priors)
    "committed": 0.55,
    "passive": 0.28,
    "churn_leaning": 0.12,
    "optout_prone": 0.06,
}
CHANNEL_EFFECT = {"email": 0.85, "sms": 1.0, "whatsapp": 1.1}     # ASSUMED
FATIGUE_MULT = {0: 1.0, 1: 0.7, 2: 0.45}                          # ASSUMED


@dataclass(slots=True)
class LatentCustomer:
    customer_id: str
    intent_archetype: str
    true_salary_day: int
    reliability: float
    responsiveness: float
    card_expiry_month: str | None
    seed_key: str


@dataclass(slots=True)
class RetryOutcome:
    success: bool
    failure_class: str | None      # canonical class when failed, else None
    latency_ms: int


def bank_operational(seed_key: str, bank: str, at: datetime) -> bool:
    """Deterministic outage calendar: per-bank Poisson windows hashed over
    (bank, 6h-bucket). A bucket is in outage when the keyed draw falls below
    the bucket hazard implied by 0.10/day ≈ 0.025 per 6h."""
    bucket = int(at.timestamp() // (6 * 3600))
    p_outage = 0.10 * (6 / 24)
    return not bernoulli(seed_key, p_outage, "outage", bank, bucket)


def balance_sufficient(seed_key: str, latent: LatentCustomer, at: datetime,
                       amount_inr: float) -> bool:
    """Salary-cycle sufficiency (documented simplification: no full ledger).
    Probability rises near the true salary day and with reliability, falls
    with amount. Draws are keyed per (customer, day)."""
    dom = at.timetuple().tm_yday
    salary_dom = latent.true_salary_day
    # distance on a 28-day payroll cycle
    dist = min((dom - salary_dom) % 30, (salary_dom - dom) % 30)
    proximity = max(0.0, 1.0 - dist / 14.0)
    amount_drag = max(0.0, 1.0 - (amount_inr / 15000.0) * 0.8)
    p = 0.15 + 0.65 * proximity * latent.reliability * (0.4 + 0.6 * amount_drag)
    return bernoulli(seed_key, min(p, 0.98), "balance", dom)


def retry_outcome(latent: LatentCustomer, *, bank: str, rail: str,
                  mandate_active: bool, amount_inr: float, failure_class: str,
                  attempt_dt: datetime, draw_key: str) -> RetryOutcome:
    """The §8 gate chain — first failing gate names the canonical class."""
    if not mandate_active:
        return RetryOutcome(False, "MANDATE_PAUSED", 120)
    if not bank_operational(latent.seed_key, bank, attempt_dt):
        return RetryOutcome(False, "BANK_TECHNICAL", 950)
    if not balance_sufficient(latent.seed_key, latent, attempt_dt, amount_inr):
        return RetryOutcome(False, "INSUFFICIENT_FUNDS", 300)
    if not bernoulli(latent.seed_key, JITTER_SUCCESS, "jitter", draw_key):
        cls = "BANK_TECHNICAL" if rail == "upi_autopay" else "RATE_LIMIT"
        return RetryOutcome(False, cls, 420)
    return RetryOutcome(True, None, 240)


def response_hazard(latent: LatentCustomer, channel: str, contacts_sent: int,
                    hours_since_failure: float) -> float:
    base = INTENT_BASE_HAZARD[latent.intent_archetype] * latent.responsiveness
    fatigue = FATIGUE_MULT.get(min(contacts_sent, 2), 0.3)
    urgency = max(0.4, 1.2 - 0.05 * hours_since_failure)   # front-loaded doctrine
    return min(0.9, base * CHANNEL_EFFECT.get(channel, 1.0) * fatigue * urgency)


def contact_response(latent: LatentCustomer, *, channel: str, contacts_sent: int,
                     hours_since_failure: float, action: str, draw_key: str
                     ) -> str | None:
    """Returns response kind or None. Branch: self_pay / reactivate / update_pm /
    opt_out (optout_prone customers can opt out on contact)."""
    h = response_hazard(latent, channel, contacts_sent, hours_since_failure)
    if not bernoulli(latent.seed_key, h, "respond", draw_key):
        return None
    rng = stream(latent.seed_key, "branch", draw_key)
    roll = rng.random()
    if latent.intent_archetype == "optout_prone" and roll < 0.35:
        return "opt_out"
    if action in ("SEND_PAYMENT_LINK", "SEND_REMINDER"):
        return "self_pay" if roll < 0.72 else "reactivate"
    if action == "REQUEST_PM_UPDATE":
        return "update_pm"
    return "self_pay"


def self_pay_succeeds(latent: LatentCustomer, at: datetime, amount_inr: float,
                      draw_key: str) -> bool:
    """A self-pay needs funds now; churn-leaning customers rarely complete."""
    if latent.intent_archetype == "churn_leaning" and bernoulli(
            latent.seed_key, 0.5, "churnskip", draw_key):
        return False
    return balance_sufficient(latent.seed_key, latent, at, amount_inr)
