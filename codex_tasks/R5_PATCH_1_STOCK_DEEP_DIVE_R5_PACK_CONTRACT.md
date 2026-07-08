# Codex Task Card — R5 Patch 1：stock-deep-dive R5 research pack contract

## 任务名称

补强 `stock-deep-dive` 的 R5 research pack 契约，让它从 R4 `stock_analysis_pack.yaml` 平滑升级/映射到 `R5_stock_research_pack.yaml`。

## 背景

Patch 0 已定义 R5 是“研究资产包 + 报告转译器”。当前 `stock-deep-dive` 主产物仍是 R4/R4+ 的 `stock_analysis_pack.yaml`。本 patch 只补 skill-local 契约、字段映射和模板引用，不写 validator、不生成报告。

## 目标

1. 在 `stock-deep-dive` 中新增 R5 research pack contract。
2. 明确 `stock_analysis_pack.yaml` 与 `R5_stock_research_pack.yaml` 的映射关系。
3. 定义 R5 的 12 个子包如何由 evidence / data-layer / valuation / market / sentiment 产物填充。
4. 定义 R5 输出状态：`R5_sample_quality_ready`、`R5_research_draft`、`R5_source_gapped_draft`、`blocked`。
5. 明确 `stock-deep-dive` 不做 evidence acquisition、不做真实 forecast 计算、不做 writer 创造。

## 允许新增 / 修改文件

- `.agents/skills/stock-deep-dive/SKILL.md`
- `.agents/skills/stock-deep-dive/references/r5_stock_research_pack_contract.md`
- `.agents/skills/stock-deep-dive/references/r5_report_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_stock_research_pack_template.yaml`
- `.agents/skills/stock-deep-dive/assets/r5_source_gap_report_template.md`
- `reports/p1_6/R5_PATCH_1_STOCK_DEEP_DIVE_R5_PACK_CONTRACT_READOUT.md`

## 禁止事项

- 不修改 `reports/workflow_runs/` 历史 run。
- 不修改已有 R4 报告正文产物，除非本任务明确要求兼容指针。
- 不新增真实 API 调用，不执行联网下载。
- 不生成任何真实股票研究报告。
- 不计算真实 forecast 或真实 valuation，除非本任务明确只做 schema fixture。
- 不把 `TODO_SOURCE_REQUIRED`、`MISSING_DISCLOSURE`、`TODO_MODEL_INPUT` 写成事实。
- 不输出买入、卖出、持有、建仓、减仓、仓位建议、保证收益或自动交易指令。
- 不让 writer / composer 创造研究结论。

## 交付物要求

`r5_stock_research_pack_contract.md` 必须包含：

- 12 个子包清单；
- 每个子包的 required / optional / blocked fields；
- `source_evidence_id`、`metric_id`、`claim_id`、`assumption_id`、`missing_reason` 规则；
- R4 `stock_analysis_pack` 到 R5 pack 的映射表；
- 降级规则；
- quality-review handoff 字段。

`SKILL.md` 只做最小增量：增加 R5 local procedure，例如 `SDD-R5-0` 到 `SDD-R5-5`，不要重写全文件。

## 验收标准

1. R5 pack contract 明确区分事实、估计、假设、推断和 source gap。
2. 所有业务、forecast、valuation、technical、sentiment 字段缺证据时必须允许 `MISSING_DISCLOSURE` / `TODO_SOURCE_REQUIRED`。
3. `stock-deep-dive` 不获得 evidence 下载职责。
4. `stock-deep-dive` 不获得真实估值计算职责；估值仍由 `company-valuation` 或已审查资产提供。
5. readout 说明本 patch 只完成契约，不声称 R5 已完成。

## 建议测试命令

~~~bash
python - <<'PY'
from pathlib import Path
required = [
    '.agents/skills/stock-deep-dive/references/r5_stock_research_pack_contract.md',
    '.agents/skills/stock-deep-dive/references/r5_report_contract.md',
    '.agents/skills/stock-deep-dive/assets/r5_stock_research_pack_template.yaml',
]
for p in required:
    assert Path(p).exists(), p
print('r5 stock-deep-dive contract files exist')
PY
~~~

## 输出要求

完成后请输出：

1. 新增 / 修改文件列表；
2. 测试命令和结果；
3. 简短 diff summary；
4. 未完成项和 source gap；
5. 一个 readout 文件，放入 `reports/p1_6/`。
