from tests.r5_bundle10r_test_fixtures import binding, model_lock
from src.report.r5_bundle10r_contracts import validate_model_generation_lock


def test_generation_binding_passes():
    result = validate_model_generation_lock(model_lock(), binding())
    assert result["decision"] == "pass"
    assert result["issue_count"] == 0


def test_stale_generation_fails():
    lock = model_lock()
    lock["generation_id"] = "model_gen_stale"
    result = validate_model_generation_lock(lock, binding())
    assert result["decision"] == "needs_fix"
    assert any(x["code"] == "model_generation_id_mismatch" for x in result["issues"])
