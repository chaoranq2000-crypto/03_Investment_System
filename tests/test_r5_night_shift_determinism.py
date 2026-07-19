from __future__ import annotations

from src.maintenance.night_shift.bf2_seed import build_seed_queue
from src.maintenance.night_shift.queue import queue_bytes
from src.maintenance.night_shift.validation import build_determinism_receipt

from tests.test_r5_night_shift_bf2_seed import synthetic_inventory


def test_bf2_seed_is_byte_for_byte_deterministic() -> None:
    inventory = synthetic_inventory()
    run_a = queue_bytes(build_seed_queue(inventory))
    run_b = queue_bytes(build_seed_queue(inventory))
    assert run_a == run_b


def test_real_night02_graph_packets_metrics_and_readout_are_deterministic(
    tmp_path,
) -> None:
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    receipt = build_determinism_receipt(
        repo_root=repo_root,
        source_commit="4340945457d661ed62967e949f862ccf2214aff2",
        output_path=tmp_path / "determinism_receipt.json",
    )
    assert receipt["all_byte_for_byte_equal"] is True
    assert len(receipt["comparisons"]) >= 10
    assert {item["artifact"] for item in receipt["comparisons"]} >= {
        "expanded_queue.yaml",
        "dependency_dag.json",
        "evidence_requests.yaml",
        "queue_metrics.json",
        "morning_readout.md",
    }
