# Codex Task Card — R5 Patch 14：orchestrator interlock and documentation index

## 任务名称

orchestrator interlock and documentation index

## 目标

1. 将 R5 spec、templates、rubric 接入 docs index。
2. 在 orchestrator spec 增加 R5 run 调度说明，但不重新定义 global workflow kernel。
3. 在 doc ownership matrix 补 R5 文件 owner。

## 允许新增 / 修改文件

- `docs/index.md`
- `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md`
- `docs/meta/DOC_OWNERSHIP_MATRIX.md`
- `docs/workflows/R5_SAMPLE_QUALITY_STOCK_REPORT_SPEC.md`（仅 cross-reference）
- `reports/p1_6/R5_PATCH_14_ORCHESTRATOR_INTERLOCK_DOC_INDEX_READOUT.md`

## 禁止事项

- 不修改 `reports/workflow_runs/` 历史 run。
- 不修改已有 R4 报告正文产物，除非本任务明确要求兼容指针。
- 不新增真实 API 调用，不执行联网下载。
- 不生成任何真实股票研究报告。
- 不计算真实 forecast 或真实 valuation，除非本任务明确只做 schema fixture。
- 不把 `TODO_SOURCE_REQUIRED`、`MISSING_DISCLOSURE`、`TODO_MODEL_INPUT` 写成事实。
- 不输出买入、卖出、持有、建仓、减仓、仓位建议、保证收益或自动交易指令。
- 不让 writer / composer 创造研究结论。

## 交付物 / 规则要求

- 不修改 `RESEARCH_WORKFLOW.md` 的 global kernel。
- R5 是 `stock-deep-dive + quality-review` 的质量层，不是新平级 workflow。
- no-advice 边界保持一致。

## 测试命令

~~~bash
python scripts/check_doc_drift.py || true
python - <<'PY'
from pathlib import Path
needles = ['R5_SAMPLE_QUALITY_STOCK_REPORT_SPEC', 'r5_stock_research_pack', 'r5_report_quality_rubric']
files = [Path('docs/index.md'), Path('docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md'), Path('docs/meta/DOC_OWNERSHIP_MATRIX.md')]
text = '
'.join(p.read_text(encoding='utf-8', errors='ignore') for p in files if p.exists())
for needle in needles:
    assert needle in text, needle
print('r5 docs interlock references exist')
PY
~~~

## 输出要求

完成后请输出：

1. 新增 / 修改文件列表；
2. 测试命令和结果；
3. 简短 diff summary；
4. 未完成项和 source gap；
5. 一个 readout 文件，放入 `reports/p1_6/`。
