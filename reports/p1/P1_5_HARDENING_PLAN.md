# P1.5 Hardening Plan

> 本内容用于研究流程与证据管理，不构成任何买入、卖出、持有或其他交易建议。

## Metadata

| Field | Value |
|---|---|
| stage | P1.5 |
| plan_date | 2026-07-01 |
| as_of_date | 2026-07-01 |
| generated_at | 2026-07-01 |
| focus | pre_p2_hardening |

## Scope

本轮只加固 P0/P1 已有工作，不进入正式 P2，不扩展新细分，不新增 P2 comparison 报告，不扩大公司池。

## Work Items

| ID | Work Item | Output | Gate |
|---|---|---|---|
| P1.5-A | 核验 Markdown/Python/TOML/YAML/CSV 可解析性 | pytest / parse checks | 无格式阻塞 |
| P1.5-B | 统一阶段状态为 P1.5 | `README.md`; `config/research_config.yaml` | stage 一致 |
| P1.5-C | 建立 draft + registry 两层 | `claims_registry.csv`; `metrics_registry.csv` | 无悬空 evidence |
| P1.5-D | 强化 evidence manifest 字段 | `evidence_manifest.csv` | source_url 与 raw_file_path 分离 |
| P1.5-E | 强化 exposure 映射字段 | `segment_company_exposure.csv`; `company_universe.csv` | verification_status 可见 |
| P1.5-F | 写死 exposure_score 规则 | `config/exposure_scoring_rules.yaml` | 技术/叙事暴露不能高分 |
| P1.5-G | 对齐 scorecard 维度 | segment / stock scorecards | 与 scoring framework 一致 |
| P1.5-H | 增加 P1.5 自动测试 | `tests/test_p1_5_hardening.py` | pytest 通过 |
| P1.5-I | 增加 CI | `.github/workflows/ci.yml` | py_compile + pytest |
| P1.5-J | 输出 hardening readout | `P1_5_HARDENING_READOUT.md` | 明确 READY_FOR_LIMITED_P2 或 blocker |

## Date Policy

- `report_date`: 研究快照日期。
- `as_of_date`: 研究使用的信息截止日期。
- `generated_at`: 文件生成日期，不得晚于 `as_of_date`。
- `due_date`、`next_review_date`、`valid_until`、`stale_after` 可以是未来日期，但必须表示任务期限、复核时间或证据过期规则。

## Exit Criteria

| Criterion | Required |
|---|---|
| P0/P1 tests | PASS |
| P1.5 hardening tests | PASS |
| stage metadata | P1.5 / pre_p2_hardening |
| high severity issue | no open high |
| medium issue | owner / due_date / blocking_for_stage present |
| P2 readiness | READY_FOR_LIMITED_P2 only after tests pass |

## Non-goals

- 不扩展新细分。
- 不新增 P2 comparison 报告。
- 不将 TODO 或 MISSING 改写成已解决。
- 不输出交易指令。
