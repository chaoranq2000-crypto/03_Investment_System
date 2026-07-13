# Bundle 10 单次人工确认卡

- workflow_id: `wf_20260703_stock_first_002837_invic`
- status: `pending_external_human_confirmation`
- purpose: 将 HR-1 至 HR-6 的复杂专业评审交给三名独立 AI 子 agent；真人只做一次哈希绑定的最终确认。
- boundary: 本文件是待确认说明，不是人工签署，也不能由自动化流程自行改成通过。

## 子 agent 已完成的工作

三名独立子 agent 已分别检查证据追溯与 claim 类型、预测与估值勾稽、叙事与风险边界。初审发现的哈希漂移、同业估值引用、重复段落、日期口径和因果措辞问题均已修复；最终对 HR-1 至 HR-6 全部建议 `pass`，剩余阻断项为 0。

- 子 agent 面板: `R5_bundle10_independent_subagent_review.yaml`
- 面板 SHA256: `63c0348bc62a0e635c7e972f323cdbb0bc2cc9b2aa66b84ae7f168edf7dfe53f`
- Reader 质量分: `98/82`
- truthfulness: `pass`
- critical blockers: `0`
- 全量回归: `637 passed, 2 skipped`

## 本次确认绑定的版本

- Reader: `R5_stock_research_report_reader_v3.md`
- Reader SHA256: `eff6f0a3d27243dc18a2fa9a144fcb4226805a1420d070b1233a9cfe08b97a83`
- 追溯附录: `R5_stock_research_report_traceability_v3.yaml`
- 追溯附录 SHA256: `7b883ffb664247ec323498db7ff995e9c7e6e0b61a0271650240fafbec385170`
- 自动评分表: `R5_stock_research_report_reader_v3_quality_scorecard.yaml`
- 自动评分表 SHA256: `23852649595386e3cc8ac5d7d8b38c1c3557713027bbbe24d91e35a3e5d0514b`

任一哈希变化都会使确认失效，必须重新评审。

## 真人只需确认四件事

1. 已完整阅读上述 Reader。
2. 已在需要处核对追溯附录，并接受或否决子 agent 对 HR-1 至 HR-6 的建议。
3. 给出真实评审人标识；评审时间可以本条确认消息的系统接收时间为准。
4. 明确总体决定与阻断意见；只有 `decision=pass` 且无阻断意见才能关闭 Bundle 10。

## 最短通过回复

只有在上述四项真实成立时，复制发送下面一句，并把 `<真实评审人标识>` 替换为本人标识：

> 确认通过；external_reviewer=<真实评审人标识>；我已完整阅读 SHA256=eff6f0a3d27243dc18a2fa9a144fcb4226805a1420d070b1233a9cfe08b97a83 的 Reader，并按需核对追溯附录；接受 SHA256=63c0348bc62a0e635c7e972f323cdbb0bc2cc9b2aa66b84ae7f168edf7dfe53f 的三名独立 AI 子 agent 面板对 HR-1 至 HR-6 的全部 pass 建议；以本条消息的系统接收时间为 reviewed_at；decision=pass；blocking_comments=[]；nonblocking_comments=[]；允许生成外部人工评审 submission 并关闭 Bundle 10；P2 保持 false。

如果不同意，直接回复 `需要修复：<问题>` 或 `否决：<原因>`；流程将保持 pending，不会关闭。

## 收到确认后的自动化动作

自动化流程只会在收到上述真实确认后执行：

1. 将已接受的 HR-1 至 HR-6 子 agent 结论映射到规范 human-review submission。
2. 写入真实评审人标识和确认消息接收时间，不伪造身份或阅读全文证明。
3. 运行 `validate_r5_bundle10_human_review_submission.py`、Reader 门、Bundle 10 关闭校验和回归测试。
4. 若任何哈希或门禁不一致，fail closed；否则关闭 Bundle 10，但仍不自动进入 P2。
