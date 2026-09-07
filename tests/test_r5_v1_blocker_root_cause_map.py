from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter, defaultdict, deque
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest
import yaml

from conftest import GIT_HISTORY


ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "reports/p1_6/r5_v1_convergence/blocker_root_cause_map.yaml"
SCHEMA_PATH = ROOT / "schemas/r5_v1_blocker_root_cause_map.schema.json"
HISTORICAL_BASELINE = "a96c1b717bf15905d72fd142efd946fa01bce666"
OCCURRENCE_REL = (
    "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/"
    "backflow/occurrence_inventory.json"
)
DAG_REL = (
    "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/"
    "backflow/dependency_dag.json"
)
QUEUE_METRICS_REL = (
    "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/"
    "backflow/queue_metrics.json"
)
NIGHT04_REL = "reports/p1_6/r5_night_shift/r5_overnight_04_20260722"
NIGHT05_REL = "reports/p1_6/r5_night_shift/r5_overnight_05_20260723"
QUEUE_REL = f"{NIGHT05_REL}/next_night_queue.yaml"


EXPECTED_BINDINGS = {
    "night02_source_queue": (
        "reports/p1_6/r5_bundle17r/activation_run_a/R5_bundle17r_backflow_queue.csv",
        "da23cb727e020946a79d4a7b93e7af00326010acb81cdfec7dfe1bbd2dd76107",
    ),
    "night02_occurrence_inventory": (
        "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/backflow/occurrence_inventory.json",
        "839afc855ad77188468f4bbada7742cb7445759136cf4d6b8abc237ff5e27213",
    ),
    "night02_dependency_dag": (
        "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/backflow/dependency_dag.json",
        "3e136a52b151c9763724bff6eb7a616672f03ce07742229435e11d6761905f6b",
    ),
    "night02_queue_metrics": (
        "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/backflow/queue_metrics.json",
        "b5255f459c1ddd04e5906eec932a89b07b1cb794c024b952abc89dd97a5d6981",
    ),
    "night04_taxonomy_audit": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/queue/taxonomy_audit.json",
        "c1164b2a9360cfa6849b419d58f4eaf594f31c17d4f7edd5d964cf5f76769711",
    ),
    "night04_truth_snapshot": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/queue/truth_snapshot.json",
        "e3213f17b14e4372e0f4a725e15b9ca331121579d842f05aed296eb11919990d",
    ),
    "night04_blocker_ledger": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/progress/blocker_ledger.json",
        "c38601fb149f5c27c597d7f20e94750761473bdbf84c2e7b69b6e21598176d4c",
    ),
    "night04_candidate_registry": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/review_control/candidate_registry.yaml",
        "c4577d21fa83951b6d7b001e1164b5e307f6bf388406a0cef7efc0c17ebf2fa1",
    ),
    "night04_dependency_recompute": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/execution/dependency_recompute.json",
        "16dd2e9dd2819bb1e1edca85e3dbdf8de5615042318e7765e7ff4b45ca05a13a",
    ),
    "night04_parent_recompute": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/execution/parent_recompute.json",
        "b5f15cf264fc8c2d8a087ed1a3eb91fa3b91eec4466ec4c5bc2c507da455e3b8",
    ),
    "night04_pointer_conflict_matrix": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/pointer_prevalidation/conflict_matrix.yaml",
        "ac1b65be239531a8d0bf2d46c2f89183d9c7f6f90d5c9b3332e31ec4f749be3f",
    ),
    "night04_pointer_dry_run_truth": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/pointer_prevalidation/dry_run_truth_receipt.json",
        "81aeaa4e4f326ab4e41ef7bb73a632dfbaaeaea6de5bdf9962c1fa9ad3354631",
    ),
    "night04_carry_forward_queue": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/next_night_queue.yaml",
        "57bef7dd3969d8b5405fdf9570e7792d11dd5b33f9a061f8664b513250f60700",
    ),
    "night05_carry_forward_queue": (
        "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/next_night_queue.yaml",
        "b7ce5bb3f1e1cd7e0081152d562583a7d89f677fac5ab66b79e2811942ce979a",
    ),
    "night05_blocker_ledger": (
        "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/progress/blocker_ledger.json",
        "114e2dac7d1f25edd2103e8c3e239177077fba61455c6c0d64862db60ff0a8d6",
    ),
    "night05_mission_state": (
        "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/mission_state.yaml",
        "3958ebee5a35df093987332f2a9e444c76c575ddea1b013054b633579586b866",
    ),
    "night05_morning_readout": (
        "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/morning_readout.json",
        "aa43cc1b4883392d3760ed1b4df73e3f6b4a0882154461f6dfed249849f112b7",
    ),
    "night05_recompute_summary": (
        "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/execution/recompute_summary.json",
        "f0611bd3afe6b65144ccd6fe4faa61815f468c2fbd3d3472037328dab755bcd1",
    ),
    "night05_change_log": (
        "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/progress/change_log.json",
        "4513964245d9f6fd3b1dbf9888d0bd815ac0e97e699b186d2db10070c6993b4f",
    ),
}

EXPECTED_BASELINE_BLOB_TRIPLETS = {
    "reports/p1_6/r5_bundle17r/activation_run_a/R5_bundle17r_backflow_queue.csv": (
        "b8a22b54cbc770ece89d0c7f972b5eaf3f2a39b6",
        25990,
        "da23cb727e020946a79d4a7b93e7af00326010acb81cdfec7dfe1bbd2dd76107",
    ),
    "reports/p1_6/r5_bundle17r/chain_a/golden_regression/R5_bundle14r_generation_lock.json": (
        "914e4bb07e59674d2196e1f6f92d9ebf04d0bd90",
        1409,
        "c98d5cc13469f8e65cf9199b3912f0a903bb2f505a04408120274ca65b2d7257",
    ),
    "reports/p1_6/r5_bundle17r/chain_a/golden_regression/R5_bundle14r_suite_result.json": (
        "a9a71286c70a1f04d1b07097bfe6ced07bc69324",
        16070,
        "b42a47581950611c0a7383aa86cd55c9144ac0d7ff55713f75b86e5deb2902d1",
    ),
    "reports/p1_6/r5_bundle17r/chain_a/materialization/R5_bundle16r_generation_lock.yaml": (
        "a284946c59ece0d259cea988f1a59c620e0a6e68",
        2126,
        "c0bea5a689003c7e50dff86c37657b3709463ffdc4976eb941d73511f7fb7ba7",
    ),
    "reports/p1_6/r5_bundle17r/chain_a/materialization/R5_bundle16r_materialization_suite.json": (
        "95f74425e23a6af961cfbc0db958a1a34e6bf6d2",
        67527,
        "167bc67074643fb4654b9d3cf4f0c0a95b943e79d579686fe19a251c39800d12",
    ),
    "reports/p1_6/r5_bundle17r/chain_a/qualification/R5_bundle15r_generation_lock.json": (
        "1437fc27d423f8a6e24b316ffd6e122e35346ba9",
        1914,
        "1e8d82a893a144c70b25fde8210119353a04bb0f515053dc1ff072a61b8321c9",
    ),
    "reports/p1_6/r5_bundle17r/chain_a/qualification/R5_bundle15r_qualification_suite.json": (
        "eeaded5644a13a005827cbfade2b88665b2dee6c",
        11521,
        "a72b5bc114fa40a552f81670f55c0411b392942e03b42a5937c2ca941f8c4c63",
    ),
    "reports/p1_6/r5_bundle17r/chain_a/qualification/qualification/golden_copper_foil_product_generation.yaml": (
        "82165ec843d5e94510e3ca5c3123213e162e0592",
        1167,
        "e9b6c961cb9a2b2ca767276d9fc476c46b93becd8e7ba934cb15d37145aafcfa",
    ),
    "reports/p1_6/r5_bundle17r/chain_a/qualification/qualification/golden_crdmo_backlog_conversion.yaml": (
        "0bbd6c9ad2917da95630fae9ca77090b5730fd2b",
        1251,
        "5e0b8b98b01a0e3207a57a9d0ea8c865dbdfd80da0e48beab59330ff76e58a72",
    ),
    "reports/p1_6/r5_bundle17r/chain_a/qualification/qualification/golden_gold_mining_cycle.yaml": (
        "5e2deca85b23f93c9cc10677176555aada1f5e00",
        1161,
        "1eeca00f4a0a6dd61f5c5c4f0c6915dcaf19a8399e7afcf51654d30fe591fb1b",
    ),
    "reports/p1_6/r5_bundle17r/chain_a/qualification/qualification/golden_multi_business_ai_infrastructure.yaml": (
        "57ae1e8244db3fc09a8a1723c1c2f1f2737748ca",
        1486,
        "e2d1d70274771f2ca62b476da0791d8053a1c170b78a9178e798da13e4726042",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/backflow/dependency_dag.json": (
        "ce2c41a568ae89e1591eb67d153458893cee46f3",
        69723,
        "3e136a52b151c9763724bff6eb7a616672f03ce07742229435e11d6761905f6b",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/backflow/occurrence_inventory.json": (
        "1f7f8858ed6b31c5c39011c1b7c06dcfa05cacfb",
        69899,
        "839afc855ad77188468f4bbada7742cb7445759136cf4d6b8abc237ff5e27213",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/backflow/queue_metrics.json": (
        "e68cb4442a7a0c71d5cd8ceb190344609a6c73f3",
        747,
        "b5255f459c1ddd04e5906eec932a89b07b1cb794c024b952abc89dd97a5d6981",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/execution/dependency_recompute.json": (
        "228d38b8a0cbdd50b897f761ebed2b06e3e274c5",
        25476,
        "16dd2e9dd2819bb1e1edca85e3dbdf8de5615042318e7765e7ff4b45ca05a13a",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/execution/parent_recompute.json": (
        "3e806de7f721d84c144b6e7dfe68ab71f4b1e5d9",
        4412,
        "b5f15cf264fc8c2d8a087ed1a3eb91fa3b91eec4466ec4c5bc2c507da455e3b8",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/next_night_queue.yaml": (
        "c06ba0b6ed8c98942bf39dde91fb4861cccadeaf",
        125858,
        "57bef7dd3969d8b5405fdf9570e7792d11dd5b33f9a061f8664b513250f60700",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/pointer_prevalidation/conflict_matrix.yaml": (
        "2a3fca7c59f0f616ae5f32d563390a3db3574247",
        8288,
        "ac1b65be239531a8d0bf2d46c2f89183d9c7f6f90d5c9b3332e31ec4f749be3f",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/pointer_prevalidation/dry_run_truth_receipt.json": (
        "752a58a41a27a479b14a200a06cc2cb7517f827e",
        367,
        "81aeaa4e4f326ab4e41ef7bb73a632dfbaaeaea6de5bdf9962c1fa9ad3354631",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/progress/blocker_ledger.json": (
        "02d9ac0f47b1e29469c2b27eec049d2da09003f2",
        23289,
        "c38601fb149f5c27c597d7f20e94750761473bdbf84c2e7b69b6e21598176d4c",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/queue/taxonomy_audit.json": (
        "0b7e83cecadf98fc2df02cb9d87bcd3966a76f85",
        839,
        "c1164b2a9360cfa6849b419d58f4eaf594f31c17d4f7edd5d964cf5f76769711",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/queue/truth_snapshot.json": (
        "42c80494449c0c75c5f1af115774a353a7bf45f4",
        823,
        "e3213f17b14e4372e0f4a725e15b9ca331121579d842f05aed296eb11919990d",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/review_control/candidate_registry.yaml": (
        "058ee50b874b00f4669876065c50e1779362b2ef",
        182988,
        "c4577d21fa83951b6d7b001e1164b5e307f6bf388406a0cef7efc0c17ebf2fa1",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/execution/recompute_summary.json": (
        "119cedbf86155cc6a0a962f8387b95e84aa4a13b",
        669,
        "f0611bd3afe6b65144ccd6fe4faa61815f468c2fbd3d3472037328dab755bcd1",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/mission_state.yaml": (
        "c0edbd67ef5a24069e2b833680b0d3ce3a30caf7",
        1002,
        "3958ebee5a35df093987332f2a9e444c76c575ddea1b013054b633579586b866",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/morning_readout.json": (
        "7b3a3477a6291f11133eadfcfb9bf4648498d1a2",
        1792,
        "aa43cc1b4883392d3760ed1b4df73e3f6b4a0882154461f6dfed249849f112b7",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/next_night_queue.yaml": (
        "055b726e6967797ac54d19e00b3344bda509005e",
        125902,
        "b7ce5bb3f1e1cd7e0081152d562583a7d89f677fac5ab66b79e2811942ce979a",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/progress/blocker_ledger.json": (
        "6bc71d68555172ca3ef19a41eb1867362b74db8f",
        1361,
        "114e2dac7d1f25edd2103e8c3e239177077fba61455c6c0d64862db60ff0a8d6",
    ),
    "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/progress/change_log.json": (
        "110d062e28ffa5c6642e130b93e96d10ea46cf21",
        463,
        "4513964245d9f6fd3b1dbf9888d0bd815ac0e97e699b186d2db10070c6993b4f",
    ),
    "reports/workflow_runs/wf_20260715_stock_first_301217_tongguan_copper_foil/bundle16r/generated/generation_lock.json": (
        "7856451f08b9cf4c220d5c89dee39aa64dde0421",
        1143,
        "02953ca1a4f932e34a1298ab3e883c66daf26fc3cffbac96c4137b764b64f461",
    ),
    "reports/workflow_runs/wf_20260715_stock_first_301217_tongguan_copper_foil/bundle16r/generated/quality_readout.json": (
        "17d3f0d20847dc8a3396d0dfb3f6914e1346e15c",
        1888,
        "0131dc5e9e3eccb233d7e6daf8edcf0e64c33396f503e28dfb502454ecad2c67",
    ),
    "reports/workflow_runs/wf_20260715_stock_first_600673_hec_tech/bundle16r/generated/generation_lock.json": (
        "339f24298dd2c65342edf9e558c22343efef0b23",
        1128,
        "cd445f4dade57e60f446dd0c5b747db4c298e4da5d2c0db11f1c4d3f9813c24e",
    ),
    "reports/workflow_runs/wf_20260715_stock_first_600673_hec_tech/bundle16r/generated/quality_readout.json": (
        "b59a5be18adf97e1a25e194c936365b6a5de867b",
        2042,
        "e4ce4d287c5a426880960eff2436391e82d87c62d66593c9abf633da985611d7",
    ),
    "reports/workflow_runs/wf_20260715_stock_first_600988_chifeng_gold/bundle16r/generated/generation_lock.json": (
        "63f8f58300372fc1dcb3f08604d8866c806c9e09",
        1134,
        "5cffa5fee240c6bb3c9f7bbf3b07d7cf4c2e8c799e1f07aa839cfb2449a3f0d1",
    ),
    "reports/workflow_runs/wf_20260715_stock_first_600988_chifeng_gold/bundle16r/generated/quality_readout.json": (
        "ff68acff69191b151e3ab6314ca2eb13e4a7d00f",
        1896,
        "ef5f0513e89e4d9f51f189fcae650e6b5ccbf02a1fe52065fba377c2e5358bf0",
    ),
    "reports/workflow_runs/wf_20260715_stock_first_603259_wuxi_apptec/bundle16r/generated/generation_lock.json": (
        "732cb0dde9babbfd7af5495c5a707592ed297481",
        1134,
        "80d673824269e8a65083e36694d4f64eaed0bd6380362cac9b25c8f6a1e0375f",
    ),
    "reports/workflow_runs/wf_20260715_stock_first_603259_wuxi_apptec/bundle16r/generated/quality_readout.json": (
        "5dc1d36e1cbc980ebe66bd6935cb1fa768635f29",
        1894,
        "a58faa678fa6150799f0ec267c46ada02df1199781ef6e61a1e18c72085bd108",
    ),
}


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def prefetch_baseline_blobs() -> None:
    GIT_HISTORY.blobs(HISTORICAL_BASELINE, EXPECTED_BASELINE_BLOB_TRIPLETS)


def git_blob_bytes(revision: str, relative_path: str) -> bytes:
    assert revision == HISTORICAL_BASELINE
    expected_oid, expected_bytes, expected_sha256 = (
        EXPECTED_BASELINE_BLOB_TRIPLETS[relative_path]
    )
    prefetch_baseline_blobs()
    blob = GIT_HISTORY.blob(revision, relative_path)
    observed_oid = blob.oid
    assert observed_oid == expected_oid, relative_path
    object_type = blob.object_type
    assert object_type == "blob", relative_path
    observed_bytes = blob.byte_count
    assert observed_bytes == expected_bytes, relative_path
    payload = blob.payload
    assert len(payload) == expected_bytes, relative_path
    assert hashlib.sha256(payload).hexdigest() == expected_sha256, relative_path
    return payload


def sha256_git_blob(revision: str, relative_path: str) -> str:
    return hashlib.sha256(git_blob_bytes(revision, relative_path)).hexdigest()


def baseline_blob_exists(relative_path: str) -> bool:
    git_blob_bytes(HISTORICAL_BASELINE, relative_path)
    return True


def load_baseline_yaml(relative_path: str) -> dict[str, Any]:
    return yaml.safe_load(
        git_blob_bytes(HISTORICAL_BASELINE, relative_path).decode("utf-8")
    )


def load_baseline_json(relative_path: str) -> dict[str, Any]:
    return json.loads(
        git_blob_bytes(HISTORICAL_BASELINE, relative_path).decode("utf-8")
    )


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    raise AssertionError(f"unsupported schema type: {expected}")


def validate_schema(
    value: Any, schema: dict[str, Any], root_schema: dict[str, Any], path: str = "$"
) -> None:
    if "$ref" in schema:
        ref = schema["$ref"]
        assert ref.startswith("#/")
        target: Any = root_schema
        for part in ref[2:].split("/"):
            target = target[part]
        validate_schema(value, target, root_schema, path)
        return

    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = (
            expected_type if isinstance(expected_type, list) else [expected_type]
        )
        assert any(_type_matches(value, item) for item in expected_types), (
            f"{path}: expected {expected_types}, got {type(value).__name__}"
        )

    if "const" in schema:
        assert value == schema["const"], f"{path}: const mismatch"
    if "enum" in schema:
        assert value in schema["enum"], f"{path}: enum mismatch {value!r}"
    if isinstance(value, str):
        if "minLength" in schema:
            assert len(value) >= schema["minLength"], f"{path}: string too short"
        if "pattern" in schema:
            assert re.fullmatch(schema["pattern"], value), f"{path}: pattern mismatch"
    if isinstance(value, int) and not isinstance(value, bool) and "minimum" in schema:
        assert value >= schema["minimum"], f"{path}: below minimum"

    if isinstance(value, dict):
        required = schema.get("required", [])
        missing = set(required) - set(value)
        assert not missing, f"{path}: missing keys {sorted(missing)}"
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            assert not extra, f"{path}: extra keys {sorted(extra)}"
        for key, item in value.items():
            if key in properties:
                validate_schema(item, properties[key], root_schema, f"{path}.{key}")

    if isinstance(value, list):
        if "minItems" in schema:
            assert len(value) >= schema["minItems"], f"{path}: too few items"
        if schema.get("uniqueItems"):
            rendered = [canonical_json_bytes(item) for item in value]
            assert len(rendered) == len(set(rendered)), f"{path}: duplicate items"
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                validate_schema(item, item_schema, root_schema, f"{path}[{index}]")


def assert_acyclic(nodes: set[str], edges: set[tuple[str, str]]) -> None:
    outgoing: dict[str, set[str]] = defaultdict(set)
    indegree = {node: 0 for node in nodes}
    for source, target in edges:
        assert source in nodes
        assert target in nodes
        assert source != target
        if target not in outgoing[source]:
            outgoing[source].add(target)
            indegree[target] += 1
    ready = deque(sorted(node for node, degree in indegree.items() if degree == 0))
    visited = 0
    while ready:
        node = ready.popleft()
        visited += 1
        for target in sorted(outgoing[node]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    assert visited == len(nodes)


def test_map_conforms_to_its_strict_dependency_free_schema() -> None:
    document = load_yaml(MAP_PATH)
    schema = load_json(SCHEMA_PATH)
    validate_schema(document, schema, schema)

    assert schema["additionalProperties"] is False
    assert schema["$defs"]["root_cause"]["additionalProperties"] is False
    assert schema["$defs"]["occurrence"]["additionalProperties"] is False
    assert schema["$defs"]["parent_work_order"]["additionalProperties"] is False
    categories = schema["$defs"]["root_cause"]["properties"]["category"]["enum"]
    assert categories == [
        "engineering_defect",
        "obtainable_evidence_gap",
        "issuer_not_disclosed",
        "human_judgment_pending",
    ]

    invalid = copy.deepcopy(document)
    invalid["unexpected"] = True
    with pytest.raises(AssertionError, match="extra keys"):
        validate_schema(invalid, schema, schema)


def test_all_source_bindings_are_exact_and_frozen_baseline_blob_bound() -> None:
    document = load_yaml(MAP_PATH)
    assert document["source_baseline"] == "a96c1b717bf15905d72fd142efd946fa01bce666"
    assert document["source_hash_representation"] == "git_blob_bytes"
    bindings = {
        item["role"]: (item["path"], item["sha256"])
        for item in document["source_bindings"]
    }
    assert bindings == EXPECTED_BINDINGS
    baseline = document["source_baseline"]
    assert baseline == HISTORICAL_BASELINE
    for relative, expected_hash in bindings.values():
        assert sha256_git_blob(baseline, relative) == expected_hash, relative


def test_occurrences_and_parents_preserve_all_69_ids_and_532_edges() -> None:
    document = load_yaml(MAP_PATH)
    inventory = load_baseline_json(OCCURRENCE_REL)
    dag = load_baseline_json(DAG_REL)
    queue = load_baseline_yaml(QUEUE_REL)
    source_occurrences = {
        item["blocker_occurrence_id"]: item for item in inventory["occurrences"]
    }
    queue_tasks = {item["id"]: item for item in queue["tasks"]}
    mapped_occurrences = {
        item["carry_forward_id"]: item for item in document["occurrences"]
    }
    mapped_parents = {
        item["carry_forward_id"]: item for item in document["parent_work_orders"]
    }

    assert len(source_occurrences) == 63
    assert len(mapped_occurrences) == 63
    assert len(mapped_parents) == 6
    assert set(mapped_occurrences) | set(mapped_parents) == set(queue_tasks)
    assert set(queue_tasks) == {item["task_id"] for item in dag["nodes"]}

    for carry_id, mapped in mapped_occurrences.items():
        source = source_occurrences[mapped["source_occurrence_id"]]
        task = queue_tasks[carry_id]
        assert task["title"].endswith(mapped["source_occurrence_id"])
        assert carry_id == (
            "ns02_t30_occ_"
            + hashlib.sha256(mapped["source_occurrence_id"].encode("utf-8")).hexdigest()[:16]
        )
        assert mapped["source_work_order_id"] == source["work_order_id"]
        assert mapped["case_id"] == source["case_id"]
        assert mapped["issuer_ticker"] == (source["issuer_ticker"] or None)
        assert mapped["source_classification"] == source["classification"]
        assert mapped["field"] == source["field"]
        assert mapped["baseline_state"] == task["night04_state"]
        assert mapped["blocked_by"] == task["depends_on"]
        assert mapped["baseline_resolved"] is False
        assert mapped["resolution_receipt_sha256"] is None
        assert mapped["source_artifact_path"] == (source["source_artifact_path"] or None)
        assert mapped["source_artifact_sha256"] == (
            source["source_artifact_sha256"] or None
        )

    for carry_id, mapped in mapped_parents.items():
        task = queue_tasks[carry_id]
        assert mapped["blocked_by"] == task["depends_on"]
        assert mapped["baseline_state"] == "parent_pending"
        assert mapped["baseline_resolved"] is False
        assert mapped["resolution_receipt_sha256"] is None
        assert f"source_work_order_id={mapped['source_work_order_id']}" in task["notes"]

    mapped_edges = {
        (dependency, carry_id)
        for carry_id, item in {**mapped_occurrences, **mapped_parents}.items()
        for dependency in item["blocked_by"]
    }
    source_edges = {(item["from"], item["to"]) for item in dag["edges"]}
    assert mapped_edges == source_edges
    assert len(mapped_edges) == 532
    assert_acyclic(set(queue_tasks), mapped_edges)


def test_dependency_groups_duplicates_and_references_are_exact_and_acyclic() -> None:
    document = load_yaml(MAP_PATH)
    queue = load_baseline_yaml(QUEUE_REL)
    queue_tasks = {item["id"]: item for item in queue["tasks"]}
    mapped = {item["carry_forward_id"]: item for item in document["occurrences"]}
    root_ids = {item["root_cause_id"] for item in document["root_causes"]}

    expected_groups: dict[str, list[str]] = {}
    for item in document["occurrences"]:
        if item["source_classification"] != "dependency_blocked":
            continue
        key = "suite" if item["case_id"] == "__suite__" else item["case_id"]
        previous = expected_groups.setdefault(key, item["blocked_by"])
        assert previous == item["blocked_by"]
    assert document["dependency_groups"] == expected_groups

    for item in document["occurrences"]:
        assert item["primary_root_id"] in root_ids
        assert all(reference in queue_tasks for reference in item["blocked_by"])
        if item["duplicate_of"] is not None:
            assert item["duplicate_of"] in mapped
            assert item["duplicate_of"] != item["carry_forward_id"]
            assert mapped[item["duplicate_of"]]["primary_root_id"] == item["primary_root_id"]

    expected_duplicates = {
        "ns02_t30_occ_6b198842cf80755a": "ns02_t30_occ_3caf2ad00e1b6285",
        "ns02_t30_occ_c7f5c80f4b2e7a9c": "ns02_t30_occ_3caf2ad00e1b6285",
        "ns02_t30_occ_c8af30bbe2f10e8a": "ns02_t30_occ_3caf2ad00e1b6285",
        "ns02_t30_occ_d2ef6aeae1113c9c": "ns02_t30_occ_99e77539490b01ad",
        "ns02_t30_occ_db819651b1640db8": "ns02_t30_occ_99e77539490b01ad",
        "ns02_t30_occ_e3fefccd3e77fd5a": "ns02_t30_occ_99e77539490b01ad",
    }
    actual_duplicates = {
        item["carry_forward_id"]: item["duplicate_of"]
        for item in document["occurrences"]
        if item["duplicate_of"] is not None
    }
    assert actual_duplicates == expected_duplicates

    conflict = load_baseline_yaml(
        f"{NIGHT04_REL}/pointer_prevalidation/conflict_matrix.yaml"
    )
    same_patch_edges = {
        frozenset((item["left"], item["right"]))
        for item in conflict["pairs"]
        if item["same_patch"]
    }
    for duplicate, canonical in actual_duplicates.items():
        assert frozenset((duplicate, canonical)) in same_patch_edges

    duplicate_edges = {(canonical, duplicate) for duplicate, canonical in actual_duplicates.items()}
    assert_acyclic(set(mapped), duplicate_edges)


def test_root_assignments_are_complete_truthful_and_leave_no_active_engineering_defect() -> None:
    document = load_yaml(MAP_PATH)
    roots = {item["root_cause_id"]: item for item in document["root_causes"]}
    assignments = Counter(item["primary_root_id"] for item in document["occurrences"])
    categories = Counter(item["category"] for item in roots.values())
    reconciliation = document["reconciliation"]

    assert len(roots) == reconciliation["root_cause_count"] == 7
    assert set(assignments) == set(roots)
    assert assignments == Counter(
        {item["root_cause_id"]: item["primary_occurrence_count"] for item in roots.values()}
    )
    assert dict(categories) == {
        "human_judgment_pending": 3,
        "obtainable_evidence_gap": 1,
        "engineering_defect": 3,
    }
    assert reconciliation["root_category_counts"] == {
        "engineering_defect": 3,
        "obtainable_evidence_gap": 1,
        "issuer_not_disclosed": 0,
        "human_judgment_pending": 3,
    }
    assert not any(item["category"] == "issuer_not_disclosed" for item in roots.values())

    open_active_engineering = [
        item
        for item in roots.values()
        if item["category"] == "engineering_defect"
        and item["status"] == "open"
        and item["affects_system_v1"]
    ]
    open_historical_engineering = [
        item
        for item in roots.values()
        if item["category"] == "engineering_defect"
        and item["status"] == "open"
        and not item["affects_system_v1"]
    ]
    assert len(open_active_engineering) == reconciliation[
        "open_active_v1_engineering_root_count"
    ] == 0
    assert len(open_historical_engineering) == reconciliation[
        "open_historical_engineering_root_count"
    ] == 3

    for item in roots.values():
        assert item["evidence_paths"]
        assert item["active_v1_evidence_paths"]
        assert all(baseline_blob_exists(path) for path in item["evidence_paths"])
        assert all((ROOT / path).is_file() for path in item["active_v1_evidence_paths"])
        if item["status"] == "resolved":
            assert item["resolution_evidence_paths"]
        else:
            assert item["resolution_evidence_paths"] == []

    ledger = load_baseline_json(f"{NIGHT05_REL}/progress/blocker_ledger.json")
    source_blocker_ids = {
        blocker_id
        for item in roots.values()
        for blocker_id in item["source_blocker_ids"]
    }
    assert source_blocker_ids == {item["blocker_id"] for item in ledger["blockers"]}

    quality_case_rows = [
        item
        for item in document["occurrences"]
        if item["field"] == "assertions.quality_case_id"
    ]
    assert len(quality_case_rows) == 4
    assert {
        item["primary_root_id"] for item in quality_case_rows
    } == {"legacy_quality_case_id_contract_gap"}


def test_source_truth_reconciles_63_20_6_69_43_0_without_fake_resolution() -> None:
    document = load_yaml(MAP_PATH)
    inventory = load_baseline_json(OCCURRENCE_REL)
    dag = load_baseline_json(DAG_REL)
    metrics = load_baseline_json(QUEUE_METRICS_REL)
    taxonomy = load_baseline_json(f"{NIGHT04_REL}/queue/taxonomy_audit.json")
    truth = load_baseline_json(f"{NIGHT04_REL}/queue/truth_snapshot.json")
    candidates = load_baseline_yaml(
        f"{NIGHT04_REL}/review_control/candidate_registry.yaml"
    )
    dependency = load_baseline_json(
        f"{NIGHT04_REL}/execution/dependency_recompute.json"
    )
    parents = load_baseline_json(f"{NIGHT04_REL}/execution/parent_recompute.json")
    pointer_truth = load_baseline_json(
        f"{NIGHT04_REL}/pointer_prevalidation/dry_run_truth_receipt.json"
    )
    queue = load_baseline_yaml(QUEUE_REL)
    mission = load_baseline_yaml(f"{NIGHT05_REL}/mission_state.yaml")
    recompute = load_baseline_json(f"{NIGHT05_REL}/execution/recompute_summary.json")
    change_log = load_baseline_json(f"{NIGHT05_REL}/progress/change_log.json")
    reconciliation = document["reconciliation"]

    assert inventory["occurrence_count"] == reconciliation["occurrence_count"] == 63
    assert dag["dependency_blocker_count"] == reconciliation[
        "dependency_blocked_occurrence_count"
    ] == 20
    assert parents["parent_count"] == reconciliation["parent_work_order_count"] == 6
    assert len(queue["tasks"]) == reconciliation["carry_forward_task_count"] == 69
    assert candidates["candidate_count"] == reconciliation["candidate_ready_count"] == 43
    assert inventory["resolved_blocker_count"] == reconciliation[
        "baseline_resolved_occurrence_count"
    ] == 0
    assert all(item["classification_is_resolution"] is False for item in inventory["occurrences"])
    assert all(item["resolved"] is False for item in inventory["occurrences"])
    assert all(item["resolution_receipt_sha256"] is None for item in inventory["occurrences"])
    assert all(item["baseline_resolved"] is False for item in document["occurrences"])

    assert metrics["total_count"] == 69
    assert metrics["ready_count"] == 0
    assert metrics["fallback_ready_count"] == 1
    assert taxonomy["night03_state_counts"] == {
        "candidate_ready": 43,
        "dependency_blocked": 20,
        "parent_pending": 6,
    }
    assert taxonomy["work_type_counts"] == {
        "analysis_required": 24,
        "bf2_work_order": 6,
        "dependency_blocked": 20,
        "engineering_local": 8,
        "evidence_required": 8,
        "human_gate": 3,
    }
    assert truth["dry_run_is_resolution"] is False
    assert truth["starting_truth"]["blocker_occurrences_resolved"] == 0
    assert truth["starting_truth"]["sample_quality_allowed"] is False
    assert truth["starting_truth"]["p2_allowed"] is False

    assert dependency["dependency_count"] == 20
    assert dependency["unlocked_count"] == dependency["resolved_count"] == 0
    assert parents["pending_parent_count"] == 6
    assert parents["resolved_parent_count"] == 0
    assert pointer_truth["resolution_receipts_emitted"] == 0
    assert pointer_truth["resolved_delta"] == 0
    assert mission["truth_boundary"]["machine_generated_decisions"] == 0
    assert mission["truth_boundary"]["sample_quality_passed"] is False
    assert mission["truth_boundary"]["p2_ready"] is False
    assert recompute["state_change_allowed"] is False
    assert recompute["trigger"] == "no_independent_passed_execution_receipts"
    assert change_log["changed_occurrence_ids"] == []
    assert change_log["changed_dependency_ids"] == []
    assert change_log["changed_parent_ids"] == []
    assert change_log["resolved_delta"] == 0

    task_ids = [item["id"] for item in queue["tasks"]]
    stable_id_hash = hashlib.sha256("\n".join(sorted(task_ids)).encode("utf-8")).hexdigest()
    task_id_set_hash = hashlib.sha256(canonical_json_bytes(task_ids)).hexdigest()
    source_hashes = [
        {
            "id": item["id"],
            "source_artifact_sha256": next(
                (
                    note.split("=", 1)[1]
                    for note in item.get("notes", [])
                    if note.startswith("source_artifact_sha256=")
                ),
                None,
            ),
        }
        for item in queue["tasks"]
    ]
    source_hash_set_hash = hashlib.sha256(canonical_json_bytes(source_hashes)).hexdigest()
    assert stable_id_hash == reconciliation["night04_stable_id_set_sha256"]
    assert task_id_set_hash == reconciliation["night05_task_id_set_sha256"]
    assert source_hash_set_hash == reconciliation["night05_source_hash_set_sha256"]


def test_source_artifact_traceability_is_preserved_including_eight_pointer_nulls() -> None:
    document = load_yaml(MAP_PATH)
    inventory = load_baseline_json(OCCURRENCE_REL)
    source_by_id = {
        item["blocker_occurrence_id"]: item for item in inventory["occurrences"]
    }
    pointer_nulls = []
    for mapped in document["occurrences"]:
        source = source_by_id[mapped["source_occurrence_id"]]
        if mapped["source_artifact_path"] is None:
            pointer_nulls.append(mapped)
            assert mapped["source_artifact_sha256"] is None
            assert mapped["source_classification"] == "engineering_local"
            match = re.search(r" in ([^:]+): '/", source["message"])
            assert match is not None
            assert baseline_blob_exists(match.group(1))
        else:
            relative = mapped["source_artifact_path"]
            assert baseline_blob_exists(relative)
            assert (
                sha256_git_blob(HISTORICAL_BASELINE, relative)
                == mapped["source_artifact_sha256"]
            )
    assert len(pointer_nulls) == 8
    assert Counter(item["field"] for item in pointer_nulls) == {
        "assertions.generation_id_present.pointer": 4,
        "assertions.quality_gate_pass.pointer": 4,
    }
