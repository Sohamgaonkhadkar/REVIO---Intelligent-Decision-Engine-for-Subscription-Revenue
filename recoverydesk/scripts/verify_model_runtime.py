"""PART A — Runtime model verification: prove the supplied XGBoost artifact is
the live scorer, end to end, in the REAL application runtime.

Chain of evidence (each step verified, none taken from a manifest label):
  1. exact artifact path resolved by the application's own resolver
  2. file exists, size
  3. SHA-256 computed independently (hashlib) vs the registered value
  4. model metadata via an INDEPENDENT xgboost.Booster load (objective,
     n trees, num_features, feature_types)
  5. activation gate passes (app's live scorer report)
  6. feature contract matches (runtime contract names/order vs artifact schema)
  7. categorical configuration matches (booster 'c' columns vs schema)
  8. real inference on a REAL live case's feature rows through the app scorer
  9. independent Booster.predict on the same rows, same vocab encoding → parity
 10. p_hat lands in the decision record (run_decision with the app scorer)
 11. the EV layer consumes exactly that p_hat (recompute EV from components)
 12. the journaled decision in PostgreSQL carries scorer_mode=active + model id

Failure path (no production artifact touched):
  F1. schema-order mismatch bundle → gate FAILS → scorer refuses activation →
      fallback doctrine priors, decisions flagged fallback
  F2. artifact-unavailable bundle → same, with 'artifact unavailable'
  F3. under fallback, constraints still deny illegal candidates (no unsafe path)

Exit code 0 only if every check passes. Report saved to
artifacts/reports/model_runtime_verification.md
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import xgboost as xgb  # noqa: E402

from core.config.loader import load_feature_contract  # noqa: E402
from core.decision.pipeline import run_decision  # noqa: E402
from core.decision.candidates import generate_candidates  # noqa: E402
from core.constraints.engine import ConstraintContext, ConstraintEngine  # noqa: E402
from core.features.builder import build_feature_row  # noqa: E402
from core.scoring.artifacts import ModelBundle, _resolve_artifact, load_manifest  # noqa: E402
from core.scoring.gate import evaluate_activation  # noqa: E402
from core.scoring.port import ScorerPort  # noqa: E402

LINES: list[str] = []
FAILED: list[str] = []


def ok(name: str, cond: bool, detail: str = "") -> bool:
    tag = "PASS" if cond else "FAIL"
    LINES.append(f"| {tag} | {name} | {detail} |")
    print(f"{tag}  {name}  — {detail}")
    if not cond:
        FAILED.append(name)
    return cond


def main() -> int:
    # ---------- the REAL application runtime scorer (same object the API uses)
    from apps.api.main import _scorer as app_scorer  # real app runtime

    manifest = load_manifest()
    rel = manifest["model_path"]
    path = _resolve_artifact(rel)

    LINES.append("# Runtime model verification — supplied XGBoost artifact")
    LINES.append("")
    LINES.append("| check | evidence |")
    LINES.append("|---|---|")

    # 1–2. path + existence
    ok("1. artifact path (app resolver)", str(path).endswith("xgboost_native_categorical_c5.json"),
       f"resolved={path} (registered={rel})")
    ok("2. artifact exists", path.exists(), f"{path.stat().st_size:,} bytes" if path.exists() else "missing")

    # 3. independent sha256
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    ok("3. SHA-256 matches registry", h == manifest["sha256"]["model"], f"{h[:24]}…")

    # 4. independent booster load → metadata
    ind = xgb.Booster()
    ind.load_model(str(path))
    cfg = json.loads(ind.save_config())
    learner = cfg["learner"]
    gb = learner["gradient_booster"]
    n_trees = int(gb["gbtree_model_param"]["num_trees"])
    booster_name = gb.get("name", "?")
    objective = learner["objective"]["name"]
    ok("4a. independent Booster loads (native JSON)", ind.num_features() == 32,
       f"num_features={ind.num_features()}, trees={n_trees}, booster={booster_name}, objective={objective}")
    ok("4b. booster is the app scorer's booster class", type(app_scorer.bundle.booster).__name__ == "Booster",
       "app bundle carries an xgboost.Booster (not a stub)")

    # 5. activation gate (live scorer)
    rep = app_scorer.activation_report
    ok("5. activation gate passes", rep["passed"] and app_scorer.active,
       f"{sum(c['passed'] for c in rep['checks'])}/{len(rep['checks'])} checks; reason='{rep['reason']}'")

    # 6. feature contract match
    contract = load_feature_contract()
    schema_names = app_scorer.bundle.feature_names
    ok("6. feature contract matches artifact schema (names+order)",
       contract.names == schema_names and len(schema_names) == 32,
       f"{len(schema_names)} features, identical order")

    # 7. categorical configuration
    model_cat = {nm for nm, tt in zip(ind.feature_names, ind.feature_types or []) if tt == "c"}
    schema_cat = set(app_scorer.bundle.categorical_features)
    ok("7. categorical config matches", model_cat == schema_cat and len(schema_cat) == 12,
       f"{len(model_cat)} 'c'-typed columns in model == {len(schema_cat)} in schema")

    # 8. real inference on a REAL live case (same snapshot the loop would wake)
    from core.orchestrator.repo import build_snapshot, load_case, rule_pack_for
    from core.clock import WallClock
    from db.engine import make_engine, make_sessionmaker
    from sqlalchemy import text
    sm = make_sessionmaker(make_engine())

    now = WallClock().now()
    snap = pack = legal = None
    case_id = None
    with sm.begin() as s2:
        cand_cases = [r.case_id for r in s2.execute(text(
            "SELECT case_id FROM recovery_cases WHERE state IN ('OPEN_DECISION','AWAITING_CUSTOMER',"
            "'WAITING') ORDER BY opened_ts DESC LIMIT 8")).fetchall()]
        cand_cases += [r.case_id for r in s2.execute(text(
            "SELECT case_id FROM recovery_cases ORDER BY opened_ts DESC LIMIT 8")).fetchall()]
        for cid in dict.fromkeys(cand_cases):          # first case with ≥1 scoreable legal candidate
            case = load_case(s2, cid)
            if case is None:
                continue
            snap_t = build_snapshot(s2, case, now)
            pack_t = rule_pack_for(s2, snap_t.rail.value)
            verdicts_t = {v.candidate_id: v for v in ConstraintEngine().evaluate_all(
                generate_candidates(snap_t, pack_t),
                ConstraintContext(snapshot=snap_t, pack=pack_t, now_utc=now))}
            legal_t = [c for c in generate_candidates(snap_t, pack_t) if verdicts_t[c.candidate_id].allowed
                       and c.action_type in ("RETRY_AT_WINDOW", "SEND_REMINDER", "SEND_PAYMENT_LINK",
                                             "REQUEST_PM_UPDATE")]
            if legal_t:
                case_id, snap, pack, legal = cid, snap_t, pack_t, legal_t
                break
    if snap is None:
        ok("8. real inference executed (app scorer, live case)", False,
           "no live case currently has a scoreable legal candidate — re-run while cases are open")
        raise SystemExit(1)
    rows = [dict(build_feature_row(snap, c).values) for c in legal]
    batch = app_scorer.score(rows, candidate_ids=[c.candidate_id for c in legal])
    ok("8. real inference executed (app scorer, live case)",
       batch.scorer_mode == "active" and batch.model_id == "c5-xgboost-native-categorical" and len(batch.p_hats) > 0,
       f"case={case_id} · {len(rows)} legal candidates scored · model={batch.model_id} v{batch.model_version}")

    # 9. independent prediction parity (same rows, same vocab semantics)
    import numpy as np
    names = app_scorer.bundle.feature_names
    cat = set(app_scorer.bundle.categorical_features)
    matrix = [[float(app_scorer.bundle.vocab_code(c, str(r[c]))) if c in cat else float(r[c])
               for c in names] for r in rows]
    dm = xgb.DMatrix(np.asarray(matrix, dtype=np.float64))
    dm.feature_names = names
    ind_probs = [float(v) for v in ind.predict(dm)]
    diff = max(abs(a - b) for a, b in zip(ind_probs, batch.p_hats))
    ok("9. independent Booster prediction == app scorer output", diff < 1e-9,
       f"max |Δp̂| = {diff:.2e} over {len(rows)} candidates; "
       f"p̂ range [{min(batch.p_hats):.4f}, {max(batch.p_hats):.4f}]")

    # 10. p_hat lands in the decision record
    result = run_decision(snap, pack, app_scorer, decision_id="verify-runtime", now_utc=now)
    rec = result.record
    scored_atoms = [a for a in rec.candidates if a.p_hat is not None and a.verdict.get("allowed")]
    by_id = {a.candidate_id: a for a in rec.candidates}
    chosen_id = rec.chosen["candidate_id"]
    chosen_atom = by_id.get(chosen_id)
    scorer_p = dict(zip(batch.candidate_ids, batch.p_hats))
    same = all(abs(by_id[cid].p_hat - scorer_p[cid]) < 1e-12 for cid in scorer_p if cid in by_id)
    ok("10. scorer p̂ appears in decision record (chosen + all scored atoms)",
       same and chosen_atom is not None and rec.fallback is False,
       f"chosen={chosen_id} p̂={chosen_atom.p_hat if chosen_atom and chosen_atom.p_hat is not None else 'policy action'} "
       f"· policy={rec.policy_id} · fallback={rec.fallback}")

    # 11. the EV layer consumed exactly that p̂
    from core.config.loader import load_costs
    costs = load_costs()
    margin = costs.value["margin_factor"]
    if chosen_atom and chosen_atom.p_hat is not None:
        comps = chosen_atom.ev_components
        exp_gain = chosen_atom.p_hat * snap.amount_at_risk * margin
        recon = exp_gain - comps["action_cost_inr"] - comps["channel_cost_inr"] \
            - comps["fatigue_cost_inr"] - comps["attempt_opportunity_cost_inr"]
        ok("11. EV layer consumes that p̂ (ev = p̂·₹·margin − costs)",
           abs(comps["expected_gain_inr"] - exp_gain) < 0.01 and abs(comps["ev_inr"] - recon) < 0.01,
           f"expected_gain={comps['expected_gain_inr']:.2f} (p̂·{snap.amount_at_risk:.0f}·{margin}) "
           f"ev={comps['ev_inr']:.2f}")
    else:
        # policy action chosen this cycle — prove it on a scored atom instead
        atom = scored_atoms[0]
        comps = atom.ev_components
        exp_gain = atom.p_hat * snap.amount_at_risk * margin
        recon = exp_gain - comps["action_cost_inr"] - comps["channel_cost_inr"] \
            - comps["fatigue_cost_inr"] - comps["attempt_opportunity_cost_inr"]
        ok("11. EV layer consumes scorer p̂ (scored atom)",
           abs(comps["expected_gain_inr"] - exp_gain) < 0.01 and abs(comps["ev_inr"] - recon) < 0.01,
           f"atom={atom.candidate_id} expected_gain={comps['expected_gain_inr']:.2f} ev={comps['ev_inr']:.2f}")

    # 11b. journaled production decisions: stored p̂ drives stored EV, end to end
    from sqlalchemy import text as _text
    with sm.begin() as s3:
        rows_j = s3.execute(_text(
            "SELECT d.case_id, d.candidates, rc.amount_at_risk "
            "FROM decision_records d JOIN recovery_cases rc USING (case_id) "
            "ORDER BY d.taken_at DESC LIMIT 60")).fetchall()
    checked, worst_gain, worst_ev, example = 0, 0.0, 0.0, None
    for r in rows_j:
        for atom in r.candidates:
            if atom.get("p_hat") is None or not atom.get("ev_components"):
                continue
            comps, ph = atom["ev_components"], atom["p_hat"]
            gain = ph * float(r.amount_at_risk) * margin
            ev_id = (comps["expected_gain_inr"] - comps["action_cost_inr"]
                     - comps["channel_cost_inr"] - comps["fatigue_cost_inr"]
                     - comps["attempt_opportunity_cost_inr"])
            checked += 1
            worst_gain = max(worst_gain, abs(comps["expected_gain_inr"] - gain))
            worst_ev = max(worst_ev, abs(comps["ev_inr"] - ev_id))
            if example is None and atom.get("verdict", {}).get("allowed"):
                example = (r.case_id, atom["candidate_id"], ph, comps["ev_inr"])
    ok("11b. journaled atoms: EV == p̂·₹·margin − costs (production records)",
       checked > 0 and worst_gain < 0.01 and worst_ev < 0.01,
       f"{checked} scored journaled atoms re-verified; max|Δgain|={worst_gain:.4f} max|Δev|={worst_ev:.4f}"
       + (f"; e.g. {example[0]} {example[1]} p̂={example[2]:.4f} ev=₹{example[3]:.2f}" if example else ""))

    # 12. journaled production decisions carry the active scorer identity
    with sm.begin() as s:
        j = s.execute(text(
            "SELECT model->>'model_id' mid, count(*) n, "
            "count(*) FILTER (WHERE model->>'mode' = 'fallback-uncalibrated') fb "
            "FROM decision_records GROUP BY 1 ORDER BY 2 DESC")).fetchall()
    active_rows = [r for r in j if r.mid == "c5-xgboost-native-categorical"]
    fallback_rows = [r for r in j if r.mid in ("doctrine-fallback",)]
    ok("12. PostgreSQL decision records carry the real model id; fallback explicitly distinct",
       len(active_rows) > 0 and all(r.fb == 0 for r in active_rows),
       "; ".join(f"{r.mid} ×{r.n} (fallback-flagged {r.fb})" for r in j)
       + (f" — separate fallback records: {sum(r.n for r in fallback_rows)}" if fallback_rows else ""))

    # ---------- failure path (production artifact untouched) ----------
    LINES.append("")
    LINES.append("## Failure path — gate refuses, fallback is explicit, constraints hold")
    LINES.append("")
    LINES.append("| check | evidence |")
    LINES.append("|---|---|")

    # F1: schema-order mismatch (transport tampered)
    tampered_schema = json.loads(json.dumps(app_scorer.bundle.schema))
    feats = tampered_schema["features"]
    feats[0], feats[1] = feats[1], feats[0]                       # reorder → mismatch
    bad_bundle = ModelBundle(manifest=manifest, schema=tampered_schema,
                             booster=app_scorer.bundle.booster)
    bad_report = evaluate_activation(bad_bundle)
    bad_scorer = ScorerPort(bad_bundle)
    ok("F1a. mismatched artifact fails the gate", not bad_report.passed and not bad_scorer.active,
       f"failed: {[c.name for c in bad_report.checks if not c.passed]}")
    fbatch = bad_scorer.score(rows, candidate_ids=[c.candidate_id for c in legal])
    ok("F1b. scorer falls back, explicitly flagged",
       fbatch.scorer_mode == "fallback" and fbatch.model_id == "doctrine-fallback"
       and fbatch.fallback_reason,
       f"model_id={fbatch.model_id} reason='{fbatch.fallback_reason}'")
    fres = run_decision(snap, pack, bad_scorer, decision_id="verify-fallback", now_utc=now)
    ok("F1c. fallback decision is flagged (policy=doctrine-b2, fallback=true)",
       fres.record.fallback is True and fres.record.policy_id == "doctrine-b2",
       f"policy={fres.record.policy_id}")

    # F2: artifact unavailable
    empty = ModelBundle(manifest=manifest, schema=app_scorer.bundle.schema, booster=None)
    empty_report = evaluate_activation(empty)
    empty_scorer = ScorerPort(empty)
    ok("F2. unavailable artifact blocks activation",
       not empty_report.passed and not empty_scorer.active and empty_scorer.score(rows).scorer_mode == "fallback",
       f"failed: {[c.name for c in empty_report.checks if not c.passed][:3]}")

    # F3: under fallback, constraints still deny illegal candidates
    snap_illegal = snap.model_copy(update={"retries_used": 3})
    v_bad = ConstraintEngine().evaluate(
        next(c for c in generate_candidates(snap_illegal, pack) if c.action_type == "RETRY_AT_WINDOW"),
        ConstraintContext(snapshot=snap_illegal, pack=pack, now_utc=now))
    fres_bad = run_decision(snap_illegal, pack, bad_scorer, decision_id="verify-fallback-illegal", now_utc=now)
    illegal_atoms = [a for a in fres_bad.record.candidates
                     if a.action_type == "RETRY_AT_WINDOW" and not a.verdict.get("allowed")]
    ok("F3. constraints enforced under fallback (retry-budget-exhausted still denied)",
       (not v_bad.allowed) and len(illegal_atoms) > 0,
       f"engine verdict: {v_bad.rule_ids} · pipeline atoms denied: {len(illegal_atoms)}")

    # ---------- report ----------
    LINES.append("")
    LINES.append(f"**Result: {len(FAILED)} failures.** "
                 f"Scorer identity: the supplied `xgboost_native_categorical_c5.json` "
                 f"(sha256 `{h[:16]}…`) loaded through the application's resolver, gate-passed, "
                 f"producing the p̂ values in live decision records and the EV inputs.")
    out = REPO / "artifacts/reports/model_runtime_verification.md"
    out.write_text("\n".join(LINES) + "\n")
    print(f"\nreport → {out}")
    print("FAILURES:", FAILED if FAILED else "none")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
