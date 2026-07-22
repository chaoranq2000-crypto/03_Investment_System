from __future__ import annotations

import hashlib
import base64

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def _lf_bytes(path) -> bytes:
    """Hash text artifacts in their declared cross-platform LF representation."""

    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def test_eight_pointer_patches_are_hash_bound_and_sandbox_only() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "pointer_prevalidation/dry_run_patch_index.yaml").read_text(encoding="utf-8"))
    assert payload["pointer_count"] == len(payload["patches"]) == 8
    assert payload["dry_run_only"] is True
    for item in payload["patches"]:
        patch = REPO_ROOT / item["patch_path"]
        encoded = _lf_bytes(patch)
        assert hashlib.sha256(encoded).hexdigest() == item["encoded_patch_sha256"]
        decoded = base64.b64decode(encoded.strip(), validate=True)
        assert hashlib.sha256(decoded).hexdigest() == item["patch_sha256"]
        assert decoded.startswith(b"diff --git")
        assert item["patch_encoding"] == "base64"
        preview = REPO_ROOT / item["forward_preview_path"]
        preview_bytes = _lf_bytes(preview)
        assert hashlib.sha256(preview_bytes).hexdigest() == item["forward_preview_sha256"]
        assert preview_bytes.startswith(b"diff --git")
        assert item["target_branch_applied"] is False
    assert len({item["patch_sha256"] for item in payload["patches"]}) == 2
