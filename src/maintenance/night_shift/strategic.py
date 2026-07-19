"""Read-only strategic fallback artifacts for the four Bundle16R golden cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from .queue import atomic_write, save_queue
from .readout import build_next_queue
from .receipts import canonical_json_bytes, sha256_bytes, sha256_file


CASE_SPECS = (
    {
        "case_id": "golden_copper_foil_product_generation",
        "ticker": "301217.SZ",
        "company": "铜冠铜箔",
        "archetype": "product_generation",
        "fixture": "tests/fixtures/r5_bundle14r/cases/copper_foil.yaml",
        "run": "reports/workflow_runs/wf_20260715_stock_first_301217_tongguan_copper_foil",
    },
    {
        "case_id": "golden_crdmo_backlog_conversion",
        "ticker": "603259.SH",
        "company": "药明康德",
        "archetype": "backlog_conversion",
        "fixture": "tests/fixtures/r5_bundle14r/cases/crdmo.yaml",
        "run": "reports/workflow_runs/wf_20260715_stock_first_603259_wuxi_apptec",
    },
    {
        "case_id": "golden_gold_mining_cycle",
        "ticker": "600988.SH",
        "company": "赤峰黄金",
        "archetype": "commodity_cycle",
        "fixture": "tests/fixtures/r5_bundle14r/cases/gold_mining.yaml",
        "run": "reports/workflow_runs/wf_20260715_stock_first_600988_chifeng_gold",
    },
    {
        "case_id": "golden_multi_business_ai_infrastructure",
        "ticker": "600673.SH",
        "company": "东阳光",
        "archetype": "multi_business_ma",
        "fixture": "tests/fixtures/r5_bundle14r/cases/multi_business_ai_infrastructure.yaml",
        "run": "reports/workflow_runs/wf_20260715_stock_first_600673_hec_tech",
    },
)

GENERATED_FILES = (
    "evidence_pack.json",
    "forecast_model.json",
    "generation_lock.json",
    "human_review.yaml",
    "operating_driver_pack.json",
    "quality_readout.json",
    "reader_report.md",
    "valuation_pack.json",
    "workflow_state.yaml",
)


def _read_structured(path: Path) -> Any:
    if path.suffix.casefold() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix.casefold() in {".yaml", ".yml"}:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    return None


def _write_json(path: Path, value: Any) -> None:
    atomic_write(
        path,
        (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
            "utf-8"
        ),
    )


def _write_yaml(path: Path, value: Any) -> None:
    atomic_write(
        path,
        yaml.safe_dump(
            value,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=1000,
            line_break="\n",
        ).encode("utf-8"),
    )


def _contains_key(value: Any, needle: str) -> bool:
    if isinstance(value, Mapping):
        return any(
            needle in str(key).casefold() or _contains_key(child, needle)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_key(child, needle) for child in value)
    return False


def build_golden_case_inventory(repo_root: Path) -> dict[str, Any]:
    cases = []
    for spec in CASE_SPECS:
        fixture_path = repo_root / str(spec["fixture"])
        fixture = _read_structured(fixture_path)
        generated_dir = repo_root / str(spec["run"]) / "bundle16r/generated"
        artifacts = []
        for filename in GENERATED_FILES:
            path = generated_dir / filename
            value = _read_structured(path) if path.suffix.casefold() != ".md" else None
            mapping = value if isinstance(value, Mapping) else {}
            artifacts.append(
                {
                    "role": path.stem,
                    "path": path.relative_to(repo_root).as_posix(),
                    "present": path.is_file(),
                    "physical_sha256": sha256_file(path) if path.is_file() else None,
                    "schema_version": mapping.get("schema_version"),
                    "artifact_type": mapping.get("artifact_type"),
                    "runtime_case_id": mapping.get("case_id"),
                    "generation_id": mapping.get("generation_id"),
                }
            )
        lock = _read_structured(generated_dir / "generation_lock.json")
        quality = _read_structured(generated_dir / "quality_readout.json")
        review = _read_structured(generated_dir / "human_review.yaml")
        missing_generation = [
            item["role"]
            for item in artifacts
            if item["role"] not in {"human_review", "reader_report"}
            and item["generation_id"] in {None, ""}
        ]
        cases.append(
            {
                "case_id": spec["case_id"],
                "ticker": spec["ticker"],
                "company": spec["company"],
                "economic_archetype": spec["archetype"],
                "bundle14r_fixture": str(spec["fixture"]),
                "bundle14r_schema_version": fixture.get("schema_version"),
                "bundle16r_run": str(spec["run"]),
                "bundle16r_runtime_case_id": lock.get("case_id"),
                "artifact_lineage": artifacts,
                "compatibility": {
                    "golden_case_id_equals_runtime_case_id": spec["case_id"]
                    == lock.get("case_id"),
                    "generation_id_complete": not missing_generation,
                    "missing_generation_id_roles": missing_generation,
                    "quality_decision": quality.get("decision"),
                    "candidate_ready_for_exact_hash_review": quality.get(
                        "candidate_ready_for_exact_hash_review"
                    ),
                    "regression_research_ready": quality.get(
                        "regression_research_ready"
                    ),
                    "sample_quality_allowed": quality.get("sample_quality_allowed"),
                    "p2_allowed": quality.get("p2_allowed"),
                    "human_review_status": review.get("status"),
                },
            }
        )
    payload: dict[str, Any] = {
        "schema_version": "r5_night_shift_golden_case_inventory_v1",
        "mode": "read_only",
        "case_count": len(cases),
        "cases": cases,
        "conclusion": "generation_and_quality_contract_gap_confirmed",
        "research_gate": "needs_targeted_backflow",
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    payload["stable_inventory_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def golden_inventory_markdown(inventory: Mapping[str, Any]) -> str:
    lines = [
        "# 四个 golden case 运行时代际盘点",
        "",
        "本盘点只读取 Bundle14R fixture 与 Bundle16R generated artifacts，不修改历史产物。",
        "",
        "| Case | Ticker | Bundle16R case_id | generation_id 完整 | 人审 | 质量/P2 |",
        "|---|---|---|---|---|---|",
    ]
    for case in inventory["cases"]:
        compatibility = case["compatibility"]
        lines.append(
            f"| `{case['case_id']}` | `{case['ticker']}` | "
            f"`{case['bundle16r_runtime_case_id']}` | "
            f"`{str(compatibility['generation_id_complete']).lower()}` | "
            f"`{compatibility['human_review_status']}` | "
            f"`sample={str(compatibility['sample_quality_allowed']).lower()}, "
            f"p2={str(compatibility['p2_allowed']).lower()}` |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- Bundle16R 物理产物存在，但 golden case ID 与 runtime case ID 属于不同代际命名。",
            "- 上游产物没有完整 `generation_id`；质量产物也缺少 Bundle17R 所需的候选就绪布尔字段。",
            "- `decision: pass` 不等于 exact-hash 人审通过，也不允许自动开放 sample quality 或 P2。",
            "",
        ]
    )
    return "\n".join(lines)


def build_driver_contract_gap_matrix(repo_root: Path) -> dict[str, Any]:
    rows = []
    for spec in CASE_SPECS:
        fixture = _read_structured(repo_root / str(spec["fixture"]))
        drivers = fixture.get("drivers", [])
        rows.append(
            {
                "case_id": spec["case_id"],
                "economic_archetype": spec["archetype"],
                "driver_count": len(drivers),
                "drivers_with_source_class": sum(
                    bool(driver.get("evidence_requirements")) for driver in drivers
                ),
                "drivers_with_unit": sum(bool(driver.get("unit")) for driver in drivers),
                "drivers_with_period_rule": sum(
                    bool(driver.get("period_rule")) for driver in drivers
                ),
                "drivers_with_financial_mapping": sum(
                    bool(driver.get("model_mapping")) for driver in drivers
                ),
                "explicit_overlap_contract_present": _contains_key(fixture, "overlap"),
                "source_locator_values_present": False,
                "period_values_present": False,
                "gap_codes": [
                    "SOURCE_LOCATOR_VALUES_PENDING",
                    "PERIOD_VALUES_PENDING",
                    *(
                        []
                        if _contains_key(fixture, "overlap")
                        else ["EXPLICIT_OVERLAP_CONTRACT_MISSING"]
                    ),
                ],
            }
        )
    return {
        "schema_version": "r5_night_shift_driver_contract_gap_matrix_v1",
        "mode": "contract_template_audit",
        "rows": rows,
        "interpretation": (
            "The Bundle14R templates declare units, period rules, source classes and model "
            "mappings; concrete source locators and period values remain evidence work."
        ),
        "resolution_claimed": False,
    }


def driver_matrix_markdown(matrix: Mapping[str, Any]) -> str:
    lines = [
        "# 四类经济驱动合同差距矩阵",
        "",
        "| Archetype | Drivers | Source class | Unit | Period rule | Financial mapping | Overlap contract |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in matrix["rows"]:
        lines.append(
            f"| `{row['economic_archetype']}` | {row['driver_count']} | "
            f"{row['drivers_with_source_class']} | {row['drivers_with_unit']} | "
            f"{row['drivers_with_period_rule']} | {row['drivers_with_financial_mapping']} | "
            f"`{str(row['explicit_overlap_contract_present']).lower()}` |"
        )
    lines.extend(
        [
            "",
            "模板层字段存在不代表证据层已完成：具体 source locator、数值期间与去重叠合同仍需逐项回流。",
            "本矩阵不构成 blocker resolution。",
            "",
        ]
    )
    return "\n".join(lines)


def _artifact_hashes_match(repo_root: Path, run_path: str) -> bool:
    generated = repo_root / run_path / "bundle16r/generated"
    lock = _read_structured(generated / "generation_lock.json")
    for role, expected in lock.get("artifact_hashes", {}).items():
        suffix = ".md" if role == "reader_report" else ".yaml" if role == "workflow_state" else ".json"
        candidate = generated / f"{role}{suffix}"
        if not candidate.is_file() or sha256_file(candidate) != expected:
            return False
    review = _read_structured(generated / "human_review.yaml")
    return review.get("generation_lock_sha256") == sha256_file(
        generated / "generation_lock.json"
    )


def build_bundle18_precheck(repo_root: Path, inventory: Mapping[str, Any]) -> dict[str, Any]:
    cases = []
    specs = {str(item["case_id"]): item for item in CASE_SPECS}
    for case in inventory["cases"]:
        compatibility = case["compatibility"]
        spec = specs[str(case["case_id"])]
        physical_hashes_match = _artifact_hashes_match(repo_root, str(spec["run"]))
        checks = {
            "candidate_artifacts_present": all(
                item["present"] for item in case["artifact_lineage"]
            ),
            "physical_hashes_match": physical_hashes_match,
            "generation_ids_complete": compatibility["generation_id_complete"],
            "candidate_ready_boolean_true": compatibility[
                "candidate_ready_for_exact_hash_review"
            ]
            is True,
            "regression_research_ready_boolean_true": compatibility[
                "regression_research_ready"
            ]
            is True,
            "human_review_pending": compatibility["human_review_status"] == "pending",
            "sample_quality_closed": compatibility["sample_quality_allowed"] is False,
            "p2_closed": compatibility["p2_allowed"] is False,
        }
        ready = all(
            checks[key]
            for key in (
                "candidate_artifacts_present",
                "physical_hashes_match",
                "generation_ids_complete",
                "candidate_ready_boolean_true",
                "regression_research_ready_boolean_true",
            )
        )
        cases.append(
            {
                "case_id": case["case_id"],
                "checks": checks,
                "eligible_for_exact_hash_review": ready,
                "status": "ready_for_human_review" if ready else "not_ready",
            }
        )
    return {
        "schema_version": "r5_night_shift_bundle18_precheck_v1",
        "overall_status": "not_ready",
        "auto_trigger": False,
        "auto_accept": False,
        "cases": cases,
        "ready_case_count": sum(item["eligible_for_exact_hash_review"] for item in cases),
        "target_case_count": len(cases),
        "research_gate": "needs_targeted_backflow",
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }


def evaluate_semantic_fixture(fixture: Mapping[str, Any]) -> tuple[str, ...]:
    issues: list[str] = []
    if int(fixture.get("word_count", 0)) >= 1000 and int(
        fixture.get("company_specific_metric_count", 0)
    ) == 0:
        issues.append("SEMANTIC_LONG_EMPTY")
    if float(fixture.get("duplicate_insight_ratio", 0.0)) > 0.25:
        issues.append("SEMANTIC_DUPLICATE")
    if bool(fixture.get("forecast_present")) and int(
        fixture.get("quantified_driver_to_financial_links", 0)
    ) == 0:
        issues.append("FORECAST_DRIVER_BRIDGE_MISSING")
    if bool(fixture.get("peer_ranking_present")) and int(
        fixture.get("qualified_peer_count", 0)
    ) < 3:
        issues.append("PEER_CONFIDENCE_UNQUALIFIED")
    if bool(fixture.get("observation_present")) and not str(
        fixture.get("falsification_condition") or ""
    ).strip():
        issues.append("OBSERVATION_NOT_FALSIFIABLE")
    return tuple(issues)


def generate_strategic_artifacts(
    *,
    repo_root: Path,
    output_dir: Path,
    occurrence_inventory_path: Path,
    source_commit: str,
) -> dict[str, Any]:
    inventory = build_golden_case_inventory(repo_root)
    matrix = build_driver_contract_gap_matrix(repo_root)
    precheck = build_bundle18_precheck(repo_root, inventory)
    occurrences = json.loads(occurrence_inventory_path.read_text(encoding="utf-8"))
    next_queue = build_next_queue(occurrences, source_commit=source_commit)

    strategic_dir = output_dir / "strategic"
    _write_yaml(strategic_dir / "golden_case_inventory.yaml", inventory)
    atomic_write(
        strategic_dir / "golden_case_inventory.md",
        golden_inventory_markdown(inventory).encode("utf-8"),
    )
    _write_yaml(strategic_dir / "driver_contract_gap_matrix.yaml", matrix)
    atomic_write(
        strategic_dir / "driver_contract_gap_matrix.md",
        driver_matrix_markdown(matrix).encode("utf-8"),
    )
    _write_yaml(strategic_dir / "bundle18_precheck.yaml", precheck)
    save_queue(strategic_dir / "night03_seed.yaml", next_queue)
    return {
        "case_count": inventory["case_count"],
        "driver_matrix_rows": len(matrix["rows"]),
        "bundle18_status": precheck["overall_status"],
        "night03_task_count": len(next_queue.tasks),
    }
