# P1.5 Hardening Readout

> 本内容用于研究流程与证据管理，不构成任何买入、卖出、持有或其他交易建议。

## Metadata

| Field | Value |
|---|---|
| stage | P1.5 |
| readout_date | 2026-07-01 |
| as_of_date | 2026-07-01 |
| generated_at | 2026-07-01 |
| status | PASS |
| p2_readiness | READY_FOR_LIMITED_P2 |

## Result

P1.5 pre-P2 hardening 已完成。当前工作区可以进入有限 P2 pilot 的准备状态，但不应直接批量扩展细分或公司池。

本轮没有新增 P2 comparison 报告，没有扩展新细分，没有删除原始证据，也没有把 TODO/MISSING 改写成已解决。

## What Changed

| Area | Status | Files |
|---|---|---|
| 阶段状态 | done | `README.md`; `config/research_config.yaml` |
| Evidence manifest | done | `data/manifests/evidence_manifest.csv` |
| Claims registry | done | `data/manifests/claims_registry.csv` |
| Metrics registry | done | `data/manifests/metrics_registry.csv` |
| Exposure verification | done | `data/processed/normalized/segment_company_exposure.csv`; `reports/segments/ai_server_liquid_cooling/company_universe.csv` |
| Exposure scoring rules | done | `config/exposure_scoring_rules.yaml` |
| Scorecard alignment | done | `reports/segments/ai_server_liquid_cooling/scorecard.yaml`; `reports/stocks/*/stock_scorecard.yaml` |
| Report scorecard consistency | done | `reports/segments/ai_server_liquid_cooling/2026-07-01_segment_report.md` |
| Quality issue gate fields | done | `reports/p1/quality_issues.csv` |
| P1.5 tests | done | `tests/test_p1_5_hardening.py` |
| CI | done | `.github/workflows/ci.yml` |

## Verification

| Command | Result |
|---|---|
| `python -m py_compile tests/test_p0_acceptance.py tests/test_p1_acceptance.py tests/test_p1_5_hardening.py` | PASS |
| `python -m pytest -q` | PASS: 23 passed |
| `conda run -p .\.conda\investment-system python -m py_compile tests/test_p0_acceptance.py tests/test_p1_acceptance.py tests/test_p1_5_hardening.py` | PASS |
| `conda run -p .\.conda\investment-system python -m pytest -q` | PASS: 23 passed |
| TOML/YAML/CSV parse check | PASS |

## Remaining TODOs

| TODO | Status | Blocking For |
|---|---|---|
| 液冷收入占比 | open | broad P2 / stock comparison confidence |
| 液冷订单或客户侧证据 | open | catalyst confidence |
| 分业务毛利率 | open | profit pool score |
| 客户认证、产能、募投证据 | open | stock deep dive depth |

## P2 Boundary

`READY_FOR_LIMITED_P2` 只表示 P1.5 工程门禁和质量门禁通过，可以设计有限 P2 pilot。它不表示研究缺口已经消失，也不表示可以直接批量铺开多个细分。

下一步如果进入 P2，应先选择 3 个以内细分做试点，并沿用本轮的 evidence manifest、claims/metrics registry、exposure scoring rules、scorecard dimensions 和 quality-review gate。
