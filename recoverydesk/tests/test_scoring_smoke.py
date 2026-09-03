"""Real-model inference smoke + honesty metadata + illegal-candidate firewall."""
import pytest

from core.config.loader import load_all_rule_packs
from core.decision.pipeline import run_decision
from core.domain.enums import FailureClass, MandateStatus
from core.features.builder import Candidate, build_feature_row, validate_row
from core.scoring.port import ScorerPort
from core.testing.fixtures import base_snapshot

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture(scope="module")
def scorer() -> ScorerPort:
    s = ScorerPort()
    assert s.active, f"real model must activate: {s.activation_report}"
    return s


def test_one_valid_row_scores_through_real_model(scorer):
    snap = base_snapshot()
    cand = Candidate(candidate_id="RETRY@W11_14", action_type="RETRY_AT_WINDOW",
                     window_code="W11_14", exec_after_hours=1.0)
    row = build_feature_row(snap, cand)
    validate_row(row.values)
    batch = scorer.score([row.values], candidate_ids=[cand.candidate_id])
    (p,) = batch.p_hats
    assert 0.0 <= p <= 1.0
    # metadata discipline (§3): every batch carries identity + honesty stamps
    assert batch.model_id == "c5-xgboost-native-categorical"
    assert batch.model_version == "1.0.0"
    assert batch.calibration_version is None
    assert batch.training_domain == "SIM"
    assert batch.scorer_mode == "active"
    assert len(batch.feature_schema_hash) == 16
    print(f"\nsmoke p̂(RETRY | INSUFFICIENT_FUNDS, hour 10 IST) = {p:.4f}")


def test_vocab_code_order_reproduces_documented_label_signal(scorer):
    """D-022 empirical verification: BANK_TECHNICAL-RETRY ≫ INSUFFICIENT_FUNDS-RETRY
    (DATASET_BUILD_REPORT §5: 88.3% vs 16.2% label-signal ordering)."""
    rows = []
    for fc in ("BANK_TECHNICAL", "INSUFFICIENT_FUNDS", "RATE_LIMIT"):
        snap = base_snapshot(failure_class_at_decision=FailureClass(fc),
                             first_failure_class=FailureClass(fc))
        row = build_feature_row(snap, Candidate(
            candidate_id=f"RETRY@{fc}", action_type="RETRY_AT_WINDOW",
            window_code="W11_14", exec_after_hours=1.0))
        rows.append(row.values)
    batch = scorer.score(rows, candidate_ids=[f"RETRY@{fc}" for fc in
                                              ("BANK_TECHNICAL", "INSUFFICIENT_FUNDS", "RATE_LIMIT")])
    p_bt, p_if, p_rl = batch.p_hats
    assert p_bt > p_if, f"code-order check failed: {p_bt:.3f} !> {p_if:.3f}"
    assert p_bt > p_rl > p_if or (p_bt > p_if and p_rl > p_if), (
        f"sanity ordering off: BT={p_bt:.3f} RL={p_rl:.3f} IF={p_if:.3f}"
    )
    print(f"\nlabel-signal check: BT={p_bt:.3f} RL={p_rl:.3f} IF={p_if:.3f}")


def test_channel_encoding_for_retry_is_unknown(scorer):
    snap = base_snapshot()
    retry_row = build_feature_row(snap, Candidate(
        candidate_id="RETRY", action_type="RETRY_AT_WINDOW")).values
    assert retry_row["channel"] == "__UNKNOWN__"          # D-021
    assert retry_row["action_type"] == "RETRY"
    remind_row = build_feature_row(snap, Candidate(
        candidate_id="R", action_type="SEND_REMINDER", channel="sms")).values
    assert remind_row["channel"] == "SMS" and remind_row["action_type"] == "SEND_REMINDER"


def test_scorer_refuses_out_of_order_rows(scorer):
    from pydantic import ValidationError

    snap = base_snapshot()
    row = dict(build_feature_row(snap, Candidate(
        candidate_id="RETRY", action_type="RETRY_AT_WINDOW")).values)
    keys = list(row.keys())
    row_swapped = {k: row[k] for k in [keys[1], keys[0]] + keys[2:]}
    with pytest.raises(Exception):
        scorer.score([row_swapped])


def test_illegal_candidates_never_reach_model():
    """The firewall, two ways:
    A) CARD_EXPIRED — generator proposes no retries at all (class-gated);
    B) INSUFFICIENT_FUNDS with mandate PAUSED — retries ARE proposed but the
       engine denies them; the spy scorer proves denied candidates never score."""
    from core.constraints.engine import ConstraintContext, ConstraintEngine
    from core.scoring.port import ScoreBatch  # noqa: F401  (identity check)

    seen_rows: list[dict] = []

    class SpyScorer(ScorerPort):
        def score(self, rows, candidate_ids=None):
            seen_rows.extend([dict(r) for r in rows])
            return super().score(rows, candidate_ids)

    spy = SpyScorer()
    assert spy.active
    pack = load_all_rule_packs()["upi_autopay_v1"]

    # A) hard class: no retry candidates proposed; link/PM-update path instead
    snap_a = base_snapshot(failure_class_at_decision=FailureClass.CARD_EXPIRED,
                           first_failure_class=FailureClass.CARD_EXPIRED)
    result_a = run_decision(snap_a, pack, spy, decision_id="d-smoke-a", now_utc=snap_a.now)
    assert not any(c.action_type == "RETRY_AT_WINDOW" for c in result_a.record.candidates)
    assert any(c.action_type == "REQUEST_PM_UPDATE" and c.verdict["allowed"]
               for c in result_a.record.candidates)
    # engine-level belt: a forced RETRY on a hard class is denied with the exact reason
    engine = ConstraintEngine()
    v = engine.evaluate(
        Candidate(candidate_id="RETRY@forced", action_type="RETRY_AT_WINDOW",
                  window_code="W11_14", exec_after_hours=1.0),
        ConstraintContext(snapshot=snap_a, pack=pack, now_utc=snap_a.now),
    )
    assert not v.allowed and any("not retry-eligible" in r for r in v.reasons)

    # B) retry-eligible class + paused mandate: proposed AND denied => never scored
    seen_rows.clear()
    snap_b = base_snapshot(mandate_status=MandateStatus.PAUSED)
    result_b = run_decision(snap_b, pack, spy, decision_id="d-smoke-b", now_utc=snap_b.now)
    proposed = [c for c in result_b.record.candidates if c.action_type == "RETRY_AT_WINDOW"]
    assert proposed, "retries are proposed for a retry-eligible class"
    assert all(not c.verdict["allowed"] for c in proposed)
    assert any("mandate paused" in r for c in proposed for r in c.verdict["reasons"])
    assert seen_rows, "scorer was called"
    assert all(r["action_type"] != "RETRY" for r in seen_rows), (
        "an illegal RETRY reached the model — firewall broken"
    )
    # chosen action is always among the LEGAL candidates
    legal_ids = {c.candidate_id for c in result_b.record.candidates if c.verdict["allowed"]}
    assert result_b.record.chosen["candidate_id"] in legal_ids


def test_fallback_mode_when_artifact_blocked():
    """Simulate a blocked gate (mismatched vocab) => doctrine fallback, honest metadata."""
    b = load_bundle_for_test()
    b.schema["category_vocab"]["rail"] = ["UPI", "__UNKNOWN__"]   # tamper
    from core.scoring.gate import evaluate_activation
    assert not evaluate_activation(b).passed
    port = ScorerPort(bundle=b)
    assert not port.active
    assert "category_vocabulary" in (port._fallback_reason or "")
    snap = base_snapshot()
    row = build_feature_row(snap, Candidate(candidate_id="RETRY", action_type="RETRY_AT_WINDOW"))
    batch = port.score([row.values], candidate_ids=["RETRY"])
    assert batch.scorer_mode == "fallback"
    assert batch.model_id == "doctrine-fallback"
    assert batch.p_hats == [pytest.approx(0.162)]   # INSUFFICIENT_FUNDS doctrine prior


def load_bundle_for_test():
    """Light copy: fresh schema object, shared manifest; booster omitted so the
    bundle is clearly inactive for scoring (fallback path under test)."""
    from core.scoring.artifacts import ModelBundle, load_bundle

    orig = load_bundle()
    import copy as _copy
    return ModelBundle(manifest=orig.manifest, schema=_copy.deepcopy(orig.schema),
                       booster=None, checks=list(orig.checks))
