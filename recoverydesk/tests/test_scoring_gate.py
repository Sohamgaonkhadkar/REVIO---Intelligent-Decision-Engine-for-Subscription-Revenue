"""Model activation gate — proven with the REAL artifact bundle (PASS) and with
tampered/broken bundles (BLOCKED with the exact failing check)."""
import copy
import json

import pytest

from core.scoring.artifacts import ArtifactCheck, ModelBundle, load_bundle, load_manifest
from core.scoring.gate import evaluate_activation

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture(scope="module")
def bundle() -> ModelBundle:
    b = load_bundle()
    assert b.schema, "schema must load for the test battery"
    return b


def test_real_bundle_internal_consistency(bundle):
    """Model's own feature_names/types == schema (measured, D-019)."""
    names = list(bundle.booster.feature_names)
    assert names == bundle.schema["features"]
    types = list(bundle.booster.feature_types)
    model_cat = {n for n, t in zip(names, types) if t == "c"}
    assert model_cat == set(bundle.categorical_features)
    assert len(names) == 32 and len(model_cat) == 12


def test_gate_passes_with_real_artifacts(bundle):
    report = evaluate_activation(bundle)
    assert report.passed, json.dumps(report.as_dict(), indent=2)
    names = [c.name for c in report.checks]
    for required in (
        "model_load", "schema_load", "schema_shape",
        "feature_names_compatible", "feature_order_compatible",
        "categorical_columns_compatible", "category_vocabulary_compatible",
        "training_domain_recorded", "calibration_status_consistent",
    ):
        assert required in names, f"gate missing check {required}"
    sha_checks = [c for c in report.checks if c.name.startswith("sha256[")]
    assert len(sha_checks) == 5 and all(c.passed for c in sha_checks)


def _light_copy(b: ModelBundle, schema=None) -> ModelBundle:
    """Share the booster; swap the schema (no Booster deepcopy)."""
    return ModelBundle(manifest=b.manifest, schema=copy.deepcopy(schema or b.schema),
                       booster=b.booster, checks=list(b.checks))


def test_gate_blocks_on_vocabulary_mismatch(bundle):
    """A schema whose vocab differs from the runtime contract => BLOCKED."""
    tampered = _light_copy(bundle)
    tampered.schema["category_vocab"]["bank_name"] = ["SBI", "HDFC", "__UNKNOWN__"]
    report = evaluate_activation(tampered)
    assert not report.passed
    failed = [c.name for c in report.checks if not c.passed]
    assert "category_vocabulary_compatible" in failed
    assert "bank_name" in next(
        c.detail for c in report.checks if c.name == "category_vocabulary_compatible"
    )


def test_gate_blocks_on_extra_feature_order_change(bundle):
    tampered = _light_copy(bundle)
    f = tampered.schema["features"]
    f[0], f[1] = f[1], f[0]  # swap order
    report = evaluate_activation(tampered)
    assert not report.passed
    failed = [c.name for c in report.checks if not c.passed]
    assert "feature_order_compatible" in failed or "feature_names_compatible" in failed


def test_gate_blocks_when_model_file_missing():
    import yaml
    from pathlib import Path
    import core.scoring.artifacts as art

    manifest = load_manifest()
    broken = copy.deepcopy(manifest)
    broken["model_path"] = "artifacts/models/c5/DOES_NOT_EXIST.json"
    (art.REPO_ROOT / "configs/registry/_test_manifest.yaml").write_text(
        yaml.safe_dump(broken)
    )
    try:
        orig = art.load_manifest

        def patched():
            return broken

        art.load_manifest = patched
        b = load_bundle()
        report = evaluate_activation(b)
        assert not report.passed
        names = [(c.name, c.passed) for c in report.checks]
        assert any(n.startswith("sha256[model]") and not p for n, p in names)
        assert ("model_load", False) in names
    finally:
        art.load_manifest = orig
        Path(art.REPO_ROOT / "configs/registry/_test_manifest.yaml").unlink(missing_ok=True)


def test_manifest_records_calibration_honesty():
    manifest = load_manifest()
    cal = manifest["calibration"]
    assert cal["calibration_version"] is None
    assert cal["mode"] == "uncalibrated"
    assert manifest["training_domain"] == "SIM"
    assert manifest["policy_allows_uncalibrated"] is True
