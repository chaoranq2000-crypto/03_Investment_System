# R5 Patch 1：R5 research pack validator 与 example

## 背景

R5 的核心不是直接写报告，而是先生成 `R5_stock_research_pack.yaml`。当前 contract 已经出现，但缺少可执行 validator 和 example。本 patch 只做 R5 research pack 的最小可校验骨架。

## 目标

1. 新增 R5 research pack example。
2. 新增 `validate_r5_stock_research_pack.py`。
3. 新增 pytest，验证 required subpacks、状态枚举、缺口显式展示、降级规则和 no-advice 边界。
4. 输出 readout。

## 允许修改文件

- `.agents/skills/stock-deep-dive/references/r5_stock_research_pack_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py`
- `tests/test_validate_r5_stock_research_pack.py`
- `reports/p1_6/R5_PATCH_1_PACK_VALIDATOR_READOUT.md`

## 禁止事项

- 不生成任何真实股票研究包。
- 不接真实数据源。
- 不修改 `reports/workflow_runs/` 历史 run。
- 不实现 forecast/valuation/technical 的计算逻辑。
- 不输出交易指令或仓位建议。
- 不把 `MISSING_DISCLOSURE`、`TODO_SOURCE_REQUIRED`、`UNVERIFIED` 改写成事实。

## 交付物

- R5 pack contract 更新。
- R5 pack example YAML。
- R5 pack validator 脚本。
- pytest。
- readout。

## 验收标准

1. example YAML 包含 12 个 subpack：company_identity_pack、evidence_snapshot_pack、financial_history_pack、business_breakdown_pack、segment_exposure_pack、industry_context_pack、peer_comparison_pack、forecast_model_pack、valuation_pack、technical_market_pack、sentiment_event_pack、risk_counterevidence_pack。
2. validator 校验 `pack_status` 枚举：`sample_quality_candidate`、`research_draft`、`blocked`、`needs_fix`。
3. 缺 forecast_model_pack 时，`sample_quality_candidate` 必须失败。
4. 缺 valuation_pack 或 market_snapshot 时，`sample_quality_candidate` 必须失败。
5. 缺 business_breakdown_pack 时，只能 `research_draft` 或更低。
6. technical / sentiment 数据缺 `as_of_date` 时，不允许输出 market-state 判断。
7. material claim 必须有 `evidence_id`、`claim_id`、`metric_id` 或 `missing_reason`。
8. pytest 通过。

## 测试命令

```bash
python .agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py .agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml
pytest tests/test_validate_r5_stock_research_pack.py
```

## 输出要求

1. 列出修改文件。
2. 列出新增文件。
3. 粘贴测试结果。
4. 列出未完成项。
5. 输出 readout 文件。
