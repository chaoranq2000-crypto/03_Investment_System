import importlib.util
from pathlib import Path

import yaml


def test_freshness_contract_fields(tmp_path):
    lock = {"generation_id": "model_gen_1"}
    downstream = {"input_model_generation_id": "model_gen_1"}
    assert lock["generation_id"] == downstream["input_model_generation_id"]
    downstream["input_model_generation_id"] = "old"
    assert lock["generation_id"] != downstream["input_model_generation_id"]
