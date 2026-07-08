# R5 Patch 31 — Source-gapped 002837 Pack Normalization

status: `TASK_CARD`

## 背景

002837 source-gapped R5 pack 已存在，并正确保留缺口，但 raw 视图显示文件物理格式为 1-2 行，且 source gap / evidence plan 可读性差。

## 目标

规范化 002837 R5 source-gapped pack、source gap report、open questions 和 evidence plan。

## 允许修改

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_pack_source_gapped.yaml
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_source_gap_report.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_open_questions.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_plan_from_gaps.yaml
tests/test_r5_source_gapped_002837_pack.py
reports/p1_6/R5_PATCH_31_SOURCE_GAPPED_002837_NORMALIZATION_READOUT.md
```

## 要求

1. YAML 必须多行可解析。
2. `pack_status` 保持 `research_draft`，不得升级。
3. `quality_status.allowed_report_level` 保持 `research_draft` 或更保守。
4. source_gap_register 必须覆盖：business、forecast、valuation、technical_market、sentiment_event、segment_exposure。
5. `forecast_model_pack.status`、`valuation_pack.status`、`technical_market_pack.status`、`sentiment_event_pack.status` 仍为 TODO，除非有 reviewed evidence。
6. no-advice 边界必须显式。

## 全局禁止事项

- 不生成任何买入、卖出、持有、建仓、减仓、仓位建议。
- 不生成 sample-quality 个股报告。
- 不进入 P2。
- 不调用 live API。
- 不把 TODO / MISSING_DISCLOSURE / LOW_CONFIDENCE_CLUE_ONLY 写成事实。
- 不用 readout 自述替代实际命令、exit_code、stdout/stderr 和 artifact evidence。


## 必跑命令

```bash
python - <<'PY'
import yaml
from pathlib import Path
for p in [
 'reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_pack_source_gapped.yaml',
 'reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_plan_from_gaps.yaml',
]:
    yaml.safe_load(Path(p).read_text(encoding='utf-8'))
print('002837 R5 YAML ok')
PY
python -m pytest -q tests/test_r5_source_gapped_002837_pack.py --tb=short
python .agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py --pack reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_pack_source_gapped.yaml
```

## 验收标准

- pack 可验证为 accepted_with_todos 或 research_draft，不得 sample-quality。
- source gaps 全部可见。
- readout 记录命令、exit_code、stdout/stderr、line_count。
