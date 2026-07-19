from __future__ import annotations

from src.maintenance.night_shift.bf2_seed import build_seed_queue
from src.maintenance.night_shift.queue import queue_bytes

from tests.test_r5_night_shift_bf2_seed import synthetic_inventory


def test_bf2_seed_is_byte_for_byte_deterministic() -> None:
    inventory = synthetic_inventory()
    run_a = queue_bytes(build_seed_queue(inventory))
    run_b = queue_bytes(build_seed_queue(inventory))
    assert run_a == run_b
