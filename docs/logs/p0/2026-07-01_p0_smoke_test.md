# P0 Smoke Test

- smoke_test_date: 2026-07-01
- scope: P0 workspace skeleton and research discipline
- result: PASS

## 1. Codex 进入项目后，是否知道这是 A 股投研工作区？

是。`AGENTS.md`、`README.md` 和 `docs/project/PROJECT_CHARTER.md` 都明确项目定位为 evidence-first A股投研工作区，不是交易系统。

## 2. 原始证据应该放在哪里？

原始证据放在 `data/raw/`，并按类型进入 `announcements/`、`annual_reports/`、`industry_reports/`、`transcripts/`、`market_data/`。`AGENTS.md` 明确 raw evidence 不可覆盖。

## 3. 处理后文本和表格应该放在哪里？

处理后文本放 `data/processed/text/`，表格放 `data/processed/tables/`，标准化记录放 `data/processed/normalized/`，嵌入或向量文件放 `data/processed/embeddings/`。

## 4. 细分报告应该放在哪里？

细分报告放 `reports/segments/<segment_id>/`，标准文件包括 `<date>_segment_report.md`、`company_universe.csv`、`scorecard.yaml`、`evidence_map.md`、`refresh_tasks.yaml`。

## 5. 个股报告应该放在哪里？

个股报告放 `reports/stocks/<stock_code>_<company_slug>/`，标准文件包括 `<date>_stock_deep_dive.md`、`segment_exposure.yaml`、`evidence_map.md`、`valuation_scenarios.*`。

## 6. 对比报告应该放在哪里？

对比报告放 `reports/comparisons/`，包括 segment comparison、stock comparison 和 score matrix。

## 7. 投资假设和复盘应该放在哪里？

投资假设放 `decisions/thesis_log.md`，watchlist 变化放 `decisions/watchlist_changes.md`，复盘放 `decisions/postmortems/`。

## 8. 一个细分如何命名？

使用英文 lower_snake_case 的稳定 `segment_id`，例如 `ai_server_liquid_cooling`。中文名只用于标题和正文。

## 9. 一个公司如何映射到多个细分？

通过 `segment_company_exposure` 多对多记录表达，字段包括 `segment_id`、`company_id`、`stock_code`、`stock_name`、`exposure_type`、`exposure_score`、`revenue_pct`、`profit_pct`、`evidence_ids`、`confidence`、`valid_from`、`valid_to`、`notes`。

## 10. 每个 skill 什么时候该用，什么时候不该用？

10 个 skill 都在 `.agents/skills/<skill-name>/SKILL.md` 中定义了 `When to use`、`Responsibilities`、`Out of scope` 和 `Guardrails`。`.codex/config.toml` 已启用这些 repo skills。

## 11. 报告模板是否要求 evidence_id？

是。`templates/segment_report.md`、`templates/stock_report.md`、`templates/evidence_card.md`、`templates/comparison_matrix.md`、`templates/investment_memo.md` 都包含 `evidence_id` 占位符和 Evidence Map。

## 12. 是否有最小质量检查规则？

是。`AGENTS.md`、`docs/policies/QUALITY_GUARDRAILS.md` 和 `.agents/skills/quality-review/SKILL.md` 都定义了证据引用、claim type、指标口径、missing data、风险反证、更新日志和非交易建议检查。

## 13. 是否明确 P0 不做复杂数据库、全市场扫描、自动估值？

是。`README.md`、`docs/project/PROJECT_CHARTER.md`、`docs/playbooks/OPERATING_PLAYBOOK.md` 和 `docs/logs/p0/2026-07-01_p0_preplanning_confirmation.md` 都明确 P0 不做复杂数据库、全市场扫描、自动抓取公告、自动估值模型、行情监控或交易策略。

## TODO

- P1 选择一个细分方向跑最小闭环。
- P1 为首个细分补真实 evidence，并把 TODO 转成 evidence_id / claim_id。

## P0 Blocking Issues

无。
