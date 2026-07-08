# R5 Patch 32 — Evidence Request Queue from R5 Gaps

status: `TASK_CARD`

## 背景

当前 `R5_evidence_plan_from_gaps.yaml` 仍是 plan-only，尚未变成可执行 evidence request queue。下一步需要把 R5 gaps 转成 evidence-ingest 能消费的队列，但不调用 live API。

## 目标

新增 source-gap 到 evidence request queue 的转换器和 fixture。

## 允许修改

```text
.agents/skills/evidence-ingest/references/r5_evidence_request_queue_contract.md
.agents/skills/evidence-ingest/scripts/build_r5_evidence_request_queue.py
tests/test_build_r5_evidence_request_queue.py
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_queue.yaml
reports/p1_6/R5_PATCH_32_EVIDENCE_REQUEST_QUEUE_READOUT.md
```

## 队列字段

每条 request 至少包含：

```yaml
request_id:
workflow_id:
stock_code:
source_gap_id:
pack_section:
evidence_need:
source_type:
source_rank:
freshness_policy:
required_for_pack:
allowed_usage:
owner_skill:
status: planned
evidence_id: null
missing_reason:
next_action:
no_live_api: true
```

## 全局禁止事项

- 不生成任何买入、卖出、持有、建仓、减仓、仓位建议。
- 不生成 sample-quality 个股报告。
- 不进入 P2。
- 不调用 live API。
- 不把 TODO / MISSING_DISCLOSURE / LOW_CONFIDENCE_CLUE_ONLY 写成事实。
- 不用 readout 自述替代实际命令、exit_code、stdout/stderr 和 artifact evidence。


## 必跑命令

```bash
python -m py_compile .agents/skills/evidence-ingest/scripts/build_r5_evidence_request_queue.py
python -m pytest -q tests/test_build_r5_evidence_request_queue.py --tb=short
python .agents/skills/evidence-ingest/scripts/build_r5_evidence_request_queue.py \
  --plan reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_plan_from_gaps.yaml \
  --out reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_queue.yaml
```

## 验收标准

- 不下载、不联网、不调用 API。
- request_id 稳定可复现。
- 每个 R5 source gap 至少转为一条 request。
- queue 多行 YAML 可解析。
