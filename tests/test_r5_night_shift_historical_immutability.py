from __future__ import annotations

import subprocess

from src.maintenance.night_shift.night04 import SOURCE_COMMIT
from tests.night04_test_support import REPO_ROOT


def test_bundle17r_night02_and_night03_history_have_zero_diff() -> None:
    paths = [
        "reports/p1_6/r5_bundle17r",
        "reports/p1_6/r5_night_shift/r5_overnight_02_20260720",
        "reports/p1_6/r5_night_shift/r5_overnight_03_20260721",
    ]
    changed = subprocess.check_output(["git", "-C", str(REPO_ROOT), "diff", "--name-only", SOURCE_COMMIT, "--", *paths], text=True).splitlines()
    assert changed == []
