# P1.5 Fix Log

> 本内容用于研究流程与证据管理，不构成任何买入、卖出、持有或其他交易建议。

## Metadata

| Field | Value |
|---|---|
| stage | P1.5 |
| log_date | 2026-07-01 |
| as_of_date | 2026-07-01 |
| generated_at | 2026-07-01 |

## Fixes

| ID | Status | Change | Files |
|---|---|---|---|
| P1.5-FIX-001 | done | 将项目阶段统一为 P1.5，并保留 P0/P1 conditional 结论 | `README.md`; `config/research_config.yaml` |
| P1.5-FIX-002 | done | 拆分 evidence manifest 的 `source_url` 与 `raw_file_path`，增加 review/archive 字段 | `data/manifests/evidence_manifest.csv` |
| P1.5-FIX-003 | done | 保留 draft 层并新增正式 registry 层 | `data/manifests/claims_registry.csv`; `data/manifests/metrics_registry.csv` |
| P1.5-FIX-004 | done | 暴露映射增加 verification 字段 | `data/processed/normalized/segment_company_exposure.csv`; `reports/segments/ai_server_liquid_cooling/company_universe.csv` |
| P1.5-FIX-005 | done | 新增 exposure_score 规则 | `config/exposure_scoring_rules.yaml` |
| P1.5-FIX-006 | done | 对齐 segment 和 stock scorecard 维度 | `reports/segments/ai_server_liquid_cooling/scorecard.yaml`; `reports/stocks/*/stock_scorecard.yaml` |
| P1.5-FIX-007 | done | 细分报告正文评分表同步补齐 8 个维度 | `reports/segments/ai_server_liquid_cooling/2026-07-01_segment_report.md` |
| P1.5-FIX-008 | done | quality issues 增加 gate 字段 | `reports/p1/quality_issues.csv` |
| P1.5-FIX-009 | done | 新增 P1.5 自动门禁测试 | `tests/test_p1_5_hardening.py` |
| P1.5-FIX-010 | done | 新增 GitHub Actions CI | `.github/workflows/ci.yml` |

## Remaining Research TODOs

| TODO | Status | Blocking For |
|---|---|---|
| 液冷收入占比 | open | broad P2 / stock comparison confidence |
| 液冷订单或客户侧证据 | open | catalyst confidence |
| 分业务毛利率 | open | profit pool score |
| 完整客户/产能/募投证据 | open | stock deep dive depth |

## Notes

本日志记录 P1.5 工程与质量门禁修复。剩余研究缺口保留为 TODO/MISSING，不作为已解决事项处理。
