# Bundle 10R Reader v5 质量门报告

## 决策

| field | value |
|---|---|
| automated decision | `candidate_ready_for_human_review` |
| score | `100 / 82` |
| truthfulness blockers | 0 |
| core-section blockers | 0 |
| candidate blockers | 0 |
| human review | `pending` |
| sample quality / P2 | `false / false` |

该决策只覆盖自动送审资格。Reader v5 尚未获得精确哈希人工通过，不得据此恢复 sample-quality 或进入 P2。

## 非补偿检查

| gate | result | evidence |
|---|---|---|
| generation binding | pass | `model_gen_r5_bundle9r_1cd42241e6a38fb3` 与 aggregate 精确匹配 |
| structured analysis units | pass | 10/10 sections；7 个 core sections 分别通过 |
| claim boundaries | pass | consensus=analyst_view；液冷独立经济性 non-additive；peer ranking=false |
| traceability | pass | 22/22 display references 唯一解析 |
| market / sentiment / event | pass | 技术与情绪有日期；未来窗口保持待官方确认 |
| narrative anti-template | pass | 七组审计标签重复=0；流程术语命中=0 |
| paragraph quality | pass | 31 个叙事段落；重复开头=0；高相似段落对=0 |
| heading coherence | pass | 6 个 H2；1.445 H2 / 1000 汉字；过薄章节=0 |
| no-advice / review truthfulness | pass | 无行动建议；人工状态为 pending |
| deterministic generation | pass | 6 个锁定产物重建两次，哈希变化=0 |

## 反馈闭环

`R5B10R-NARRATIVE-001` 已由 Reader v5 和 v2 叙事合同解决。Reader v4 的原文件及 generation lock 未改写；用户反馈单独记录为 `R5_bundle10r_human_feedback_v4.yaml`，且明确 `full_review_attested=false`。

新的人工复核 TODO 为 `R5B10R-V5-HUMAN-001`。审核对象是 Reader v5 SHA256 `cb261412f1c72dfd56e6dc9030c3d0f8bb06d4963a5525396059a6b1a21e6090`，handoff SHA256 `6bbd352bd1fb6fec58095ca204465516b0923169d98b30eb2d5a5d9a29e7cccd`。

## 保留问题

- DCF 缺少完整可审阅的净债务、折现率与终值输入。
- SOTP 缺少液冷独立经济性、未分配成本与消除关系。
- v5 精确哈希人工复核待完成。
- 未获发布授权，因此不声明远端 CI。
