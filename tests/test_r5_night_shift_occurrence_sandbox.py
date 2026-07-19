from __future__ import annotations

import pytest

from src.maintenance.night_shift.night03 import Night03Error
from src.maintenance.night_shift.night03_execution import validate_occurrence_diff


def test_pointer_child_diff_must_be_a_subset_of_exact_approved_paths() -> None:
    result = validate_occurrence_diff(
        ["src/maintenance/night_shift/night03.py"],
        approved_paths=["src/maintenance/night_shift/**"],
        forbidden_paths=["data/raw/**"],
    )
    assert result["passed"] is True
    with pytest.raises(Night03Error, match="escaped approved scope"):
        validate_occurrence_diff(
            ["src/maintenance/night_shift/night03.py", "data/raw/fabricated.json"],
            approved_paths=["src/maintenance/night_shift/**"],
            forbidden_paths=["data/raw/**"],
        )
