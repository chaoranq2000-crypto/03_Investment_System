# Codex Task Card — R5 Patch 39：evidence request queue review ledger

## 任务名称

evidence request queue review ledger

## 背景

`R5_evidence_request_queue.yaml` 已存在，但状态仍是 planned，且多个 request 的 `evidence_id: null`。下一步需要建立 review ledger，把 request 的处理状态显式化：pending / rejected / accepted / needs_manual_collection。只有 accepted request 才能作为 reviewed input registry 的来源。

## 目标

1. 新增 R5 evidence request review ledger schema。
2. 为 002837 workflow run 生成 `R5_evidence_request_review_ledger.yaml`。
3. 新增 builder：从 `R5_evidence_request_queue.yaml` 生成初始 ledger，不联网，不补事实。
4. 新增 validator：accepted 必须有 evidence_id；pending 必须有 missing_reason 和 next_action。

## 允许新增 / 修改文件

- `.agents/skills/evidence-ingest/references/r5_evidence_request_review_ledger_contract.md`
- `.agents/skills/evidence-ingest/assets/r5_evidence_request_review_ledger.example.yaml`
- `.agents/skills/evidence-ingest/scripts/build_r5_evidence_request_review_ledger.py`
- `.agents/skills/evidence-ingest/scripts/validate_r5_evidence_request_review_ledger.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_review_ledger.yaml`
- `tests/test_build_r5_evidence_request_review_ledger.py`
- `tests/test_validate_r5_evidence_request_review_ledger.py`
- `reports/p1_6/R5_PATCH_39_EVIDENCE_REQUEST_REVIEW_LEDGER_READOUT.md`

## 禁止事项

- 不下载、抓取或伪造新证据。
- 不把 queue 中 `evidence_id: null` 的 request 改成 accepted。
- 不删除 source gaps。
- 不修改 evidence_manifest，除非本任务明确要求新增 ledger 引用；默认不修改。
- 不生成报告结论。

## Ledger 要求

```yaml
schema_version: r5_evidence_request_review_ledger_v0.1
artifact_type: R5_evidence_request_review_ledger
workflow_id: wf_20260703_stock_first_002837_invic
source_queue_path: reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_queue.yaml
review_status: pending
items:
  - request_id: <from queue>
    source_gap_id: <from queue>
    pack_section: <from queue>
    review_decision: pending
    evidence_id: null
    reason: TODO_SOURCE_REQUIRED
    next_action: manual source collection required before promotion
promotion_rules:
  - accepted requires evidence_id and source_rank
  - pending cannot unblock source-gapped pilot
```

## 验收标准

1. builder 可从当前 queue 生成 ledger。
2. validator 能拒绝 accepted-but-null-evidence 的记录。
3. ledger 不改变 queue 原始含义，只增加 review 状态。
4. readiness / close gate 可以读取 ledger 作为输入状态，但不应自动放行。
5. readout 明确列出 pending 项数量。

## 测试命令

```bash
python -m py_compile .agents/skills/evidence-ingest/scripts/build_r5_evidence_request_review_ledger.py .agents/skills/evidence-ingest/scripts/validate_r5_evidence_request_review_ledger.py
python .agents/skills/evidence-ingest/scripts/build_r5_evidence_request_review_ledger.py --queue reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_queue.yaml --out reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_review_ledger.yaml
python .agents/skills/evidence-ingest/scripts/validate_r5_evidence_request_review_ledger.py reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_review_ledger.yaml
pytest -q tests/test_build_r5_evidence_request_review_ledger.py tests/test_validate_r5_evidence_request_review_ledger.py --tb=short
```

## 输出要求

完成后输出：新增/修改文件、测试结果、diff summary、pending count、readout 路径。
