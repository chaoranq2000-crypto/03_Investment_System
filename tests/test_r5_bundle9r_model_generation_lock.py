from pathlib import Path

import yaml

from src.research.r5_bundle9r_contracts import sha256_file, stable_aggregate


def test_model_lock_aggregate_is_order_stable(tmp_path):
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    a.write_text("a: 1\n", encoding="utf-8")
    b.write_text("b: 2\n", encoding="utf-8")
    rows1 = sorted([{"path": str(a), "sha256": sha256_file(a)}, {"path": str(b), "sha256": sha256_file(b)}], key=lambda x: x["path"])
    rows2 = sorted(reversed(rows1), key=lambda x: x["path"])
    assert stable_aggregate(rows1) == stable_aggregate(rows2)
