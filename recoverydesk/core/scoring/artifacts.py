"""Model artifact bundle — load, verify, expose. NEVER fabricate.

Bundle (from configs/registry/model_artifacts.yaml):
  * xgboost booster JSON (loaded via xgboost.Booster — no pickle conversion)
  * schema (JSON transport of the canonical joblib; D-019)
  * sha256 verification of every file
  * internal-consistency checks (model feature_names/types vs schema)

Calibration honesty: calibration_version is None and mode is 'uncalibrated'
unless a separately versioned calibration artifact is configured — none exists.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(slots=True)
class ArtifactCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass(slots=True)
class ModelBundle:
    manifest: dict[str, Any]
    schema: dict[str, Any]
    booster: Any = None                      # xgboost.Booster when loaded
    checks: list[ArtifactCheck] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks) and self.booster is not None

    @property
    def feature_names(self) -> list[str]:
        return list(self.schema["features"])

    @property
    def categorical_features(self) -> list[str]:
        return list(self.schema["categorical_features"])

    @property
    def category_vocab(self) -> dict[str, list[str]]:
        return {k: list(v) for k, v in self.schema["category_vocab"].items()}

    @property
    def numeric_features(self) -> list[str]:
        cat = set(self.categorical_features)
        return [f for f in self.feature_names if f not in cat]

    def vocab_code(self, column: str, value: str) -> int:
        """Category -> training code (D-022: vocab index order, fail-closed)."""
        vocab = self.category_vocab.get(column)
        if vocab is None:
            raise ValueError(f"{column} is not categorical")
        if value in vocab:
            return vocab.index(value)
        return vocab.index("__UNKNOWN__")


def load_manifest() -> dict[str, Any]:
    path = REPO_ROOT / "configs/registry/model_artifacts.yaml"
    return yaml.safe_load(path.read_text())


def _resolve_artifact(rel: str):
    """Resolve an artifact path: repo-relative first, then the sandbox
    single-source fallback (uploads/) — no duplicate copies (D-026/D-029)."""
    cand = REPO_ROOT / rel
    if cand.exists() or rel.startswith("/"):
        return cand
    import pathlib

    up = REPO_ROOT.parent / "uploads" / pathlib.Path(rel).name
    return up if up.exists() else cand


def load_bundle(*, load_model: bool = True) -> ModelBundle:
    """Load + verify the artifact bundle; every failure is a recorded check."""
    manifest = load_manifest()
    checks: list[ArtifactCheck] = []
    schema: dict[str, Any] = {}
    booster = None

    # 1. schema loadable + internally consistent
    schema_path = _resolve_artifact(manifest["schema_path"])
    try:
        schema = json.loads(schema_path.read_text())
        assert set(schema.keys()) >= {"features", "categorical_features", "category_vocab"}
        checks.append(ArtifactCheck("schema_load", True, f"{len(schema['features'])} features"))
    except Exception as exc:
        checks.append(ArtifactCheck("schema_load", False, str(exc)[:200]))
        return ModelBundle(manifest=manifest, schema={}, booster=None, checks=checks)

    exp = manifest["expected_counts"]
    n, ncat = len(schema["features"]), len(schema["categorical_features"])
    if (n, ncat) == (exp["features"], exp["categorical"]) and set(schema["category_vocab"]) == set(schema["categorical_features"]):
        checks.append(ArtifactCheck("schema_shape", True, f"{n} features / {ncat} categorical / {n - ncat} numeric"))
    else:
        checks.append(ArtifactCheck("schema_shape", False, f"got {n}/{ncat}, expected {exp['features']}/{exp['categorical']}"))
        return ModelBundle(manifest=manifest, schema=schema, booster=None, checks=checks)

    # 2. sha256 of every registered file
    for label, rel in {
        "model": manifest["model_path"],
        "schema": manifest["schema_path"],
        "best_params": "artifacts/reports/c5_xgb_native_categorical/best_params.json",
        "metrics": "artifacts/reports/c5_xgb_native_categorical/native_categorical_metrics.csv",
        "optuna_trials": "artifacts/reports/c5_xgb_native_categorical/optuna_trials.csv",
    }.items():
        p = _resolve_artifact(rel)
        expected = manifest["sha256"][label]
        actual = _sha256(p) if p.exists() else "MISSING"
        checks.append(ArtifactCheck(f"sha256[{label}]", actual == expected,
                                    f"{actual[:16]}… vs {expected[:16]}…"))

    # 3. model load + model↔schema consistency
    if load_model:
        try:
            import xgboost as xgb

            booster = xgb.Booster()
            booster.load_model(str(_resolve_artifact(manifest["model_path"])))
            names_ok = list(booster.feature_names) == list(schema["features"])
            checks.append(ArtifactCheck("model_load", True, f"{booster.num_features()} features"))
            checks.append(ArtifactCheck(
                "model_feature_names_match_schema", names_ok,
                "" if names_ok else "booster feature_names != schema features (or order)"))
            cat_set = set(schema["categorical_features"])
            types = list(booster.feature_types or [])
            if types:
                model_cat = {nm for nm, tt in zip(booster.feature_names, types) if tt == "c"}
                checks.append(ArtifactCheck(
                    "model_categorical_types_match_schema", model_cat == cat_set,
                    f"model c-cols {len(model_cat)} vs schema {len(cat_set)}"))
        except Exception as exc:
            checks.append(ArtifactCheck("model_load", False, str(exc)[:200]))
            booster = None

    return ModelBundle(manifest=manifest, schema=schema, booster=booster, checks=checks)
