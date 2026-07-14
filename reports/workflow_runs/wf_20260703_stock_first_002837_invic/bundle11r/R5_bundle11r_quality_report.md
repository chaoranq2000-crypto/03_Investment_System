# R5 Bundle 11R 质量报告

> 历史兼容标记：早期 `quality_gate_report.md` 中的 pre-Bundle 7 快照为 `historical_snapshot_superseded_by_bundle7_quality_rebaseline`；其替代质量面保存在 `R5_bundle7_quality_gate_report.md`。本文件当前正文记录11R前向候选，不改写该历史关系。

## 结论

自动范围结论为 `accepted_with_todos`。002837真实输入 runtime 为 `candidate_inputs_ready`，经营驱动通过，同业方法限定为背景，语义检查通过，未生成研究回流任务。新Reader为 `candidate_ready_for_human_review`；真实人工复核仍为 `pending`。

## 可复核事实

| check | result |
|---|---|
| research questions | total=12；bounded_estimate=6；optional missing=6；critical_open=0 |
| operating driver | pass；三情景、三期间、三条宽产品线 |
| 9R reconciliation | 9/9；收入最大差额=2.3e-05 CNY；毛利最大差额=0.010076 CNY |
| proxy boundary | 最高占比=9.52%；低于45%上限 |
| peer method | eligible=0；同业倍数未启用 |
| semantic gate | candidate_ready；critical/high/medium=0/0/0 |
| Reader gate | score=100/82；truth/core/candidate blockers=0/0/0 |
| references | 28/28 resolved |
| exact report hash | `0c059bf4e5b81f98052a0172fc2d0c25419a52f723b0295cc684765381cd372f` |
| full regression | 724 passed, 2 skipped, 30.94s |

## 证据与推断边界

- `metric_company_cn_002837_invic_precision_thermal_management_sales_volume_2025A_11r` 是2025A公司级报告事实，值为324,058 units；不得解释为液冷或分部出货。
- 机房与机柜温控的等价销量、公司级混合单价和未来量价矩阵属于低置信度 `estimate`，用于解释既有9R宽产品线预测。
- 其他业务是显式 `proxy`；基准2026E占收入约9.32%。
- 4家候选同业均缺少同经营定义、收入纯度、会计边界和预测日期，因而只作背景。
- 液冷独立收入、毛利、项目数、单位价值、验收周期、重叠消除和营运资金保持 `MISSING/TODO`，未被猜测填补。

## 保留事项

`R5_bundle11r_quality_issues.csv` 记录14项门禁结果：critical/high为0；经营证据、分部指标、重叠消除、独立暴露、同业方法、DCF、SOTP与精确哈希人工复核作为medium/low TODO保留。所有事项均有owner和下一步。

## 边界

旧Reader v5的人审结论不转移到新哈希。`sample_quality_allowed=false`，`p2_allowed=false`。本文不构成投资建议。
