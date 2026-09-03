"""ScorerPort — model-agnostic probability port (invariant 10).

Modes:
  * active   — real XGBoost artifact serves p̂ for LEGAL candidates only
               (the decision pipeline guarantees illegals never reach scoring)
  * fallback — deterministic doctrine priors (registered, DATA_DERIVED), the
               system keeps working; constraints remain authoritative; every
               batch is stamped scorer_mode=fallback with the reason

Every ScoreBatch carries (model_id, model_version, calibration_version,
training_domain, feature_schema_hash, scorer_mode) and is journaled into the
decision record (PHASE_4 §9.1 metadata discipline).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from core.config.loader import load_registry
from core.scoring.artifacts import ModelBundle, load_bundle
from core.scoring.gate import evaluate_activation

MODEL_ID = "c5-xgboost-native-categorical"
MODEL_VERSION = "1.0.0"


@dataclass(slots=True)
class ScoreBatch:
    p_hats: list[float]
    model_id: str
    model_version: str
    calibration_version: str | None
    training_domain: str
    feature_schema_hash: str
    scorer_mode: str                      # active | fallback
    fallback_reason: str | None = None
    candidate_ids: list[str] = field(default_factory=list)

    def metadata(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "calibration_version": self.calibration_version,
            "training_domain": self.training_domain,
            "feature_schema_hash": self.feature_schema_hash,
            "mode": self.scorer_mode,
        }


class ScoringError(RuntimeError):
    pass


class ScorerPort:
    """score(feasible_rows) -> ScoreBatch. Rows are contract-validated dicts in
    schema order (built by core.features for LEGAL candidates only)."""

    def __init__(self, bundle: ModelBundle | None = None):
        self._bundle = bundle or load_bundle()
        self._report = evaluate_activation(self._bundle)
        self._active = self._report.passed and self._bundle.all_passed
        self._fallback_reason = None if self._active else (self._report.reason or "artifact unavailable")

    # ------------------------------------------------------------------ info
    @property
    def active(self) -> bool:
        return self._active

    @property
    def activation_report(self) -> dict:
        return self._report.as_dict()

    @property
    def bundle(self) -> ModelBundle:
        return self._bundle

    # ----------------------------------------------------------------- score
    def score(self, rows: Sequence[dict[str, Any]], candidate_ids: Sequence[str] | None = None
              ) -> ScoreBatch:
        if not rows:
            return self._empty_batch()
        if self._active:
            p = self._score_active(rows)
        else:
            p = [self._doctrine_p_hat(r) for r in rows]
        return ScoreBatch(
            p_hats=p,
            model_id=MODEL_ID if self._active else "doctrine-fallback",
            model_version=MODEL_VERSION if self._active else "b2-doctrine-1",
            calibration_version=None if not self._active
            else self._bundle.manifest["calibration"]["calibration_version"],
            training_domain="SIM",
            feature_schema_hash=self._schema_hash(),
            scorer_mode="active" if self._active else "fallback",
            fallback_reason=self._fallback_reason,
            candidate_ids=list(candidate_ids or []),
        )

    # -------------------------------------------------------------- internals
    def _score_active(self, rows: Sequence[dict[str, Any]]) -> list[float]:
        import numpy as xgb_np

        names = self._bundle.feature_names
        cat = self._bundle.categorical_features
        matrix = []
        for row in rows:
            if list(row.keys()) != names:
                raise ScoringError(
                    "feature row does not match schema order — refusing to score "
                    f"(got {len(row)} fields, schema has {len(names)})"
                )
            matrix.append([
                float(self._bundle.vocab_code(c, str(row[c]))) if c in cat else float(row[c])
                for c in names
            ])
        import xgboost as xgb

        dm = xgb.DMatrix(xgb_np.asarray(matrix, dtype=xgb_np.float64))
        dm.feature_names = names
        probs = self._bundle.booster.predict(dm)
        return [float(v) for v in probs]

    def _doctrine_p_hat(self, row: dict[str, Any]) -> float:
        """Deterministic doctrine priors (fallback). Registered in the assumption
        registry; RETRY-by-class values are DATA_DERIVED from DATASET_BUILD_REPORT
        §5 label-signal sanity; contact actions use the conservative mart base rate."""
        reg = load_registry()
        table: dict[str, Any] = reg.entries["doctrine_fallback_p_hat"].value
        action = row.get("action_type", "__UNKNOWN__")
        failure = row.get("failure_class_at_decision", "__UNKNOWN__")
        retry_by_class = table["retry_by_class"]
        if action == "RETRY":
            return float(retry_by_class.get(failure, table["default_contact"]))
        return float(table["default_contact"])

    def _empty_batch(self) -> ScoreBatch:
        return ScoreBatch(
            p_hats=[], model_id="none", model_version="0", calibration_version=None,
            training_domain="SIM", feature_schema_hash=self._schema_hash(),
            scorer_mode="active" if self._active else "fallback",
            fallback_reason=self._fallback_reason,
        )

    def _schema_hash(self) -> str:
        if self._bundle.schema:
            from core.config.loader import content_hash

            return content_hash(self._bundle.schema)[:16]
        return "none"
