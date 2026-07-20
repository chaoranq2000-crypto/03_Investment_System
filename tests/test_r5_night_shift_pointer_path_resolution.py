from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_all_pointer_paths_are_exact_relative_and_existing() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "pointer_prevalidation/path_resolution.yaml").read_text(encoding="utf-8"))
    assert payload["pointer_count"] == 8
    for item in payload["records"]:
        assert item["passed"] is True
        assert item["exact_allowed_paths"] == [
            "scripts/build_r5_bundle16r_case_pack.py",
            "tests/test_r5_bundle16r_case_pack_builder.py",
        ]
        assert all((REPO_ROOT / path).is_file() for path in item["exact_allowed_paths"])
        assert all("*" not in path for path in item["exact_allowed_paths"])
