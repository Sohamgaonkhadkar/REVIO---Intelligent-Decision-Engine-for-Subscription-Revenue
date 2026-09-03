"""Model activation gate — the sole authority on whether the real scorer may serve.

Gate checks (all must pass; any failure => scorer stays in flagged fallback and
the Model page reports BLOCKED with the exact failing checks):
  1. model load
  2. schema load (+ internal shape/vocab consistency)
  3. feature-NAME compatibility  (runtime contract names == artifact schema)
  4. feature-ORDER compatibility (exact sequence)
  5. categorical-COLUMN compatibility
  6. category-VOCABULARY compatibility (exact lists, exact order)
  7. sha256 artifact verification (every registered file)
  8. training-domain metadata (training_domain == "SIM", disclosed per policy)
  9. calibration status (calibration_version must be null + mode uncalibrated
     unless a real calibration artifact is configured; V1 policy flag must
     explicitly permit uncalibrated probabilities)
"""
from __future__ import annotations

from dataclasses import dataclass

from core.config.loader import load_feature_contract
from core.scoring.artifacts import ArtifactCheck, ModelBundle, load_bundle


@dataclass(slots=True)
class ActivationReport:
    passed: bool
    checks: list[ArtifactCheck]
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail} for c in self.checks
            ],
        }


def evaluate_activation(bundle: ModelBundle | None = None) -> ActivationReport:
    bundle = bundle or load_bundle()
    checks: list[ArtifactCheck] = list(bundle.checks)

    if bundle.schema:
        # 3–6: runtime feature contract vs artifact schema (exact equality).
        # These checks do NOT require the booster — a schema mismatch must
        # block regardless of whether the model binary itself loaded.
        contract = load_feature_contract()
        rt_names = contract.names
        sc_names = bundle.feature_names
        checks.append(ArtifactCheck(
            "feature_names_compatible", rt_names == sc_names,
            "" if rt_names == sc_names else
            f"runtime has {len(rt_names)} names; artifact has {len(sc_names)}; "
            f"only-runtime={sorted(set(rt_names) - set(sc_names))[:6]}, "
            f"only-artifact={sorted(set(sc_names) - set(rt_names))[:6]}"))
        checks.append(ArtifactCheck(
            "feature_order_compatible", rt_names == sc_names,
            "" if rt_names == sc_names else "same names, different order (or names differ)"))
        rt_cat = [f.name for f in contract.categorical]
        sc_cat = bundle.categorical_features
        checks.append(ArtifactCheck(
            "categorical_columns_compatible", rt_cat == sc_cat,
            "" if rt_cat == sc_cat else f"runtime {rt_cat} != artifact {sc_cat}"))
        vocab_ok, vocab_detail = True, ""
        for f in contract.categorical:
            art_vocab = bundle.category_vocab.get(f.name)
            if f.vocab != art_vocab:
                vocab_ok = False
                vocab_detail += f"{f.name}: runtime {f.vocab} != artifact {art_vocab}; "
        checks.append(ArtifactCheck("category_vocabulary_compatible", vocab_ok, vocab_detail))

    # model presence: the loader records model_load; a hand-built bundle must
    # still prove a booster exists before activation may pass
    if not any(c.name in ("model_load", "model_loaded") for c in checks):
        checks.append(ArtifactCheck("model_loaded", bundle.booster is not None,
                                    "no booster attached to bundle"))

    # 8: training domain must be recorded and disclosed as SIM
    td = bundle.manifest.get("training_domain")
    checks.append(ArtifactCheck(
        "training_domain_recorded", td == "SIM", f"training_domain={td!r}"))

    # 9: calibration honesty + policy gate for uncalibrated probabilities
    cal = bundle.manifest.get("calibration", {})
    cal_version = cal.get("calibration_version")
    cal_mode = cal.get("mode")
    allowed = bundle.manifest.get("policy_allows_uncalibrated") is True
    cal_ok = (cal_version is None and cal_mode == "uncalibrated" and allowed) or (
        cal_version is not None and cal_mode == "calibrated")
    checks.append(ArtifactCheck(
        "calibration_status_consistent", cal_ok,
        f"calibration_version={cal_version}, mode={cal_mode}, "
        f"policy_allows_uncalibrated={allowed}"))

    passed = all(c.passed for c in checks)
    failed = [c.name for c in checks if not c.passed]
    return ActivationReport(
        passed=passed,
        checks=checks,
        reason="" if passed else "failed checks: " + ", ".join(failed),
    )
