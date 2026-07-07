# R5 Next Stage Summary Readout - Patch 9, 10, 11

## Result

Status: `patch_9_10_11_completed`

本组按 `codex_tasks/r5_next_stage/APPLY_ORDER.md` 完成 evidence-ingest R5 stock evidence plan、R5 close readout / task queue templates、sample report benchmark placeholder policy。

未生成真实个股研究结论，未调用 live API，未修改历史 `reports/workflow_runs/` 产物。

## Files added or changed

- `.agents/skills/evidence-ingest/references/r5_stock_evidence_plan_contract.md`
- `.agents/skills/evidence-ingest/assets/r5_stock_evidence_plan.example.yaml`
- `.agents/skills/evidence-ingest/scripts/validate_r5_stock_evidence_plan.py`
- `tests/test_validate_r5_stock_evidence_plan.py`
- `reports/p1_6/R5_PATCH_9_EVIDENCE_PLAN_READOUT.md`
- `templates/r5_workflow_close_readout.md`
- `templates/r5_source_gap_report.md`
- `templates/r5_open_questions.md`
- `templates/r5_task_queue.md`
- `tests/test_r5_close_readout_templates.py`
- `reports/p1_6/R5_PATCH_10_CLOSE_READOUT_TEMPLATE_READOUT.md`
- `benchmarks/sample_reports/README.md`
- `benchmarks/sample_reports/sample_report_metadata.schema.yaml`
- `benchmarks/sample_reports/section_expectation_mapping.yaml`
- `tests/test_sample_report_benchmark_policy.py`
- `reports/p1_6/R5_PATCH_11_SAMPLE_BENCHMARK_POLICY_READOUT.md`

## Test results

```text
pytest tests/test_validate_r5_stock_evidence_plan.py
6 passed

pytest tests/test_r5_close_readout_templates.py
5 passed

pytest tests/test_sample_report_benchmark_policy.py
4 passed
```

## Source gaps and remaining work

- Evidence plan 只定义证据需求、缺口和归档计划，不把计划项写成已验证事实。
- Close readout 模板要求保留 source gap、open questions、next tasks 与 owner/severity/next step。
- Patch 12 company-valuation mini validator 由最终验收 readout 一并收束。
