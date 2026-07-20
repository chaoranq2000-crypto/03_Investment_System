from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_generation_lock_previews_bind_proposal_patch_and_base() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "pointer_prevalidation/generation_lock_previews.yaml").read_text(encoding="utf-8"))
    assert payload["preview_count"] == len(payload["previews"]) == 8
    assert len({item["preview_generation_id"] for item in payload["previews"]}) == 8
    assert all(len(item["proposal_sha256"]) == len(item["sandbox_patch_sha256"]) == 64 for item in payload["previews"])
    assert all(item["resolution_receipt_emitted"] is False for item in payload["previews"])
