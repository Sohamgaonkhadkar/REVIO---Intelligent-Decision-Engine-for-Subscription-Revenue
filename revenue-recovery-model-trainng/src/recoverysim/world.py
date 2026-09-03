"""Latent world processes (SEALED semantics — policies never see this module's truth).

Design: content-addressable keyed draws make world state a pure function of
(seed, entity, time), so every policy run observes the SAME world (common
random numbers => paired policy comparisons) without shared mutable state.

Processes:
  - balance sufficiency: correlated per salary cycle (cycle luck), boosted
    after salary, degraded before salary; amount-sensitive.
  - bank outages: per (bank, day) Poisson start count, Exp durations.
  - mandate lifecycle: user pause/revoke (UPI), card expiry, lost/stolen.
"""

import math

import numpy as np

from recoverysim.domain import FailureClass, PaymentRail
from recoverysim.random import keyed

DAYS_PER_MONTH = 30


class World:
    def __init__(self, seed: int, sim_days: int, costs: dict | None = None):
        self.seed = seed
        self.sim_days = sim_days
        self._outage_cache: dict = {}
        self.suff = (costs or {}).get("sufficiency", {})
        self.refresh_p = float((costs or {}).get("card_silent_refresh_prob", 0.97))
        self.outage = (costs or {}).get("outage",
                                       {"lambda_per_day": 0.10, "duration_mean_h": 1.5,
                                        "duration_min_h": 0.5, "duration_max_h": 6.0})
        self.jitter_p = float((costs or {}).get("renewal_jitter_p", 0.01))
        self.lifecycle = (costs or {}).get("mandate_lifecycle", {})

    # ---------- balance sufficiency (lazy balance-ledger simplification) ----------
    def sufficient(self, customer_id: int, day: int, salary_day: int, reliability: float,
                   amount: float, rail: str = "UPI_AUTOPAY") -> bool:
        """Is the customer's account able to cover a debit of `amount` on `day`?
        Correlated within a salary cycle via per-cycle luck; same inputs => same answer."""
        s = self.suff
        cycle = math.floor((day - salary_day) / DAYS_PER_MONTH)
        day_off = (day - salary_day) % DAYS_PER_MONTH          # 0 = salary day
        if rail == "CARD_SI":
            p = s.get("base_card", 0.975) + s.get("rel_mult_card", 0.02) * reliability
        else:
            p = s.get("base_upi", 0.74) + s.get("rel_mult_upi", 0.24) * reliability
        if 0 <= day_off <= 4:                                   # post-salary flush
            p += s.get("post_salary_boost", 0.30)
        if (salary_day - day) % DAYS_PER_MONTH in (1, 2, 3):    # pre-salary depletion
            p -= s.get("pre_salary_penalty", 0.35)
        pen = s.get("amount_log_penalty", 0.05)
        ref = s.get("amount_ref", 300.0)
        p *= float(np.clip(1.0 - pen * math.log2(max(amount, 1) / ref), 0.70, 1.08))
        p = float(np.clip(p, s.get("clamp_lo", 0.01), s.get("clamp_hi", 0.995)))
        luck = keyed(self.seed, "cycleluck", customer_id, cycle).random()
        return luck < p

    # ---------- bank outages ----------
    def _outages_for(self, bank: str, day: int) -> list[tuple[int, int]]:
        key = (bank, day)
        if key not in self._outage_cache:
            rng = keyed(self.seed, "outage", bank, day)
            n = rng.poisson(float(self.outage.get("lambda_per_day", 0.10)))  # ASSUMED
            spans = []
            for _ in range(min(n, 3)):
                start = int(rng.integers(0, 24))
                dur = float(np.clip(rng.exponential(float(self.outage.get("duration_mean_h", 1.5))),
                                    float(self.outage.get("duration_min_h", 0.5)),
                                    float(self.outage.get("duration_max_h", 6.0))))
                spans.append((start, math.ceil(start + dur)))
            self._outage_cache[key] = spans
        return self._outage_cache[key]

    def bank_down(self, bank: str, day: int, hour: int) -> bool:
        return any(start <= hour <= end for start, end in self._outages_for(bank, day))

    # ---------- mandate / instrument lifecycle ----------
    def instrument_states(self, sub: dict, intent: str) -> dict:
        """Precompute per-month latent instrument state for a subscription.
        Returns dict month_index -> status string + pause metadata."""
        rng = keyed(self.seed, "mandate", sub["subscription_id"])
        months = self.sim_days // DAYS_PER_MONTH
        out: dict[int, dict] = {}
        revoked_from = None
        lost_from = None
        pause_until_day = -1
        card_expiry_month = None

        if sub["rail"] == PaymentRail.CARD_SI:
            # card expiry ~ uniform over 36-month validity (ASSUMED); network
            # tokenization / account updater silently refreshes most (costs cfg)
            raw_expiry = int(rng.integers(1, 37))
            if rng.random() < getattr(self, "refresh_p", 0.97):
                card_expiry_month = None      # silently refreshed (tokenization)
            else:
                card_expiry_month = raw_expiry
            u_lost = rng.random()
            if u_lost < 0.004 and lost_from is None:  # ASSUMED rare lost/stolen
                lost_from = int(rng.integers(0, months))

        # monthly hazards by intent (ASSUMED rates, config-driven after calibration)
        lc = self.lifecycle
        p_pause = float(lc.get("p_pause", {}).get(intent, 0.008))
        p_revoke = float(lc.get("p_revoke", {}).get(intent, 0.003))

        for m in range(months):
            month_start = m * DAYS_PER_MONTH
            status = "ACTIVE"
            if revoked_from is not None and month_start >= revoked_from:
                status = "CLOSED"
            elif lost_from is not None and month_start >= lost_from:
                status = "LOST"
            elif (sub["rail"] == PaymentRail.CARD_SI and card_expiry_month is not None
                  and m >= card_expiry_month):
                status = "EXPIRED"
            elif sub["rail"] == PaymentRail.UPI_AUTOPAY:
                if month_start < pause_until_day:
                    status = "PAUSED"
                u = rng.random()
                if status != "PAUSED" and u < p_pause:
                    dur = math.inf if (intent == "CHURN_LEANING" and rng.random() < 0.6) \
                        else float(np.clip(rng.exponential(8.0), 2, 30))
                    pause_until_day = math.inf if dur is math.inf else month_start + int(dur)
                    status = "PAUSED" if month_start < pause_until_day else "PAUSED"
                    out[m] = {"status": "PAUSED", "pause_end_day": pause_until_day}
                if status != "PAUSED" and revoked_from is None and rng.random() < p_revoke:
                    revoked_from = month_start
                    status = "CLOSED"
            if m not in out:
                out[m] = {"status": status, "pause_end_day": pause_until_day if status == "PAUSED" else -1}
        return out


def renewal_outcome(world: World, seed: int, sub: dict, cust_latent: dict, inst_state: dict,
                    ts_h: int) -> tuple[bool, FailureClass | None]:
    """Structural first-attempt outcome at renewal time ts_h (hour index)."""
    day = ts_h // 24
    hour = ts_h % 24
    month = day // DAYS_PER_MONTH
    status = inst_state.get(month, {"status": "ACTIVE"})["status"]
    if status == "CLOSED":
        return False, FailureClass.MANDATE_CLOSED
    if status == "PAUSED":
        return False, FailureClass.MANDATE_PAUSED
    if status == "EXPIRED":
        return False, FailureClass.CARD_EXPIRED
    if status == "LOST":
        return False, FailureClass.CARD_LOST_STOLEN
    if world.bank_down(sub["bank_name"], day, hour):
        return False, FailureClass.BANK_TECHNICAL
    if not world.sufficient(sub["customer_id"], day, cust_latent["salary_day"],
                            cust_latent["reliability"], sub["plan_amount_inr"],
                            rail=sub["rail"]):
        return False, FailureClass.INSUFFICIENT_FUNDS
    jitter = keyed(seed, "jitter", sub["subscription_id"], month).random()
    if jitter < world.jitter_p:  # ASSUMED residual issuer noise (config-calibrated)
        return False, FailureClass.BANK_TECHNICAL
    return True, None
