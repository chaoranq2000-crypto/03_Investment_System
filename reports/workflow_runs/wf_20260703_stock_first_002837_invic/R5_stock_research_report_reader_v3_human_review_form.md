# R5 Reader v3 外部人工评审表

- workflow_id: `wf_20260703_stock_first_002837_invic`
- form_status: `pending_external_human_review`
- boundary: 本表由自动化流程预填待审信息，不构成人工签署。

## 哈希绑定输入

- Reader: `C:/Projects/03_Investment_System/reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_report_reader_v3.md`
- Reader SHA256: `eff6f0a3d27243dc18a2fa9a144fcb4226805a1420d070b1233a9cfe08b97a83`
- 追溯附录: `C:/Projects/03_Investment_System/reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_report_traceability_v3.yaml`
- 追溯附录 SHA256: `7b883ffb664247ec323498db7ff995e9c7e6e0b61a0271650240fafbec385170`
- 自动评分表: `C:/Projects/03_Investment_System/reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_report_reader_v3_quality_scorecard.yaml`
- 自动评分表 SHA256: `23852649595386e3cc8ac5d7d8b38c1c3557713027bbbe24d91e35a3e5d0514b`
- 机器可读提交模板: `C:/Projects/03_Investment_System/reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_report_reader_v3_human_review_submission_template.yaml`

## 评审步骤

1. 独立阅读 Reader，并按需核对追溯附录与自动评分表。
2. 确认正在审阅的 Reader SHA256 与本表一致；如不一致，停止签署并重新生成评审包。
3. 对 HR-1 至 HR-6 分别填写 `pass` 或 `needs_fix`，不得保留 `pending`。
4. 填写真实评审人标识、评审时间、总体决定以及阻断/非阻断意见，并同步填写机器可读提交模板。
5. 只有六项均为 `pass`、总体决定为 `pass`、无阻断意见且哈希一致，才可提交最终关闭。

## 必填检查表

| check_id | 检查问题 | 评审结果 | 评审意见 |
|---|---|---|---|
| HR-1 | 核心观点是否与证据和边界一致 | `pending` |  |
| HR-2 | 事实估计推断管理层表述与分析师观点是否易于区分 | `pending` |  |
| HR-3 | 预测与估值假设是否清楚且不过度精确 | `pending` |  |
| HR-4 | 风险反证和观察条件是否足以推翻核心判断 | `pending` |  |
| HR-5 | 技术情绪事件是否只作为市场上下文 | `pending` |  |
| HR-6 | 正文是否清晰可读且无内部机器字段 | `pending` |  |

## 人工签署（全部必填）

- external_reviewer: `<required>`
- reviewed_at: `<required, ISO-8601>`
- decision: `<required: pass / needs_fix / reject>`
- report_sha256_confirmed: `eff6f0a3d27243dc18a2fa9a144fcb4226805a1420d070b1233a9cfe08b97a83`
- blocking_comments: `<required; 无则填写 none>`
- nonblocking_comments: `<required; 无则填写 none>`

## 校验与关闭命令

先复制提交模板为 `R5_stock_research_report_reader_v3_human_review_submission.yaml` 并由真实评审人填写，然后执行：

```powershell
.\.conda\investment-system\python.exe scripts/validate_r5_bundle10_human_review_submission.py --repo-root . --submission reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_report_reader_v3_human_review_submission.yaml
.\.conda\investment-system\python.exe scripts/finalize_r5_bundle10_after_human_review.py --repo-root . --submission reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_report_reader_v3_human_review_submission.yaml --confirm-finalize
```

## 提交边界

签署后应复制并填写 YAML 提交模板，不要把模板原件或 pending handoff 直接改成通过。随后运行人工提交校验、Reader 门、Bundle 10 关闭校验和全量回归。任何报告内容变化都会使本次评审失效。
