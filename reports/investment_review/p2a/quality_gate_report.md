# P2A quality gate report

## 结论

状态：`accepted_with_todos`

P2A 组合上下文补丁满足精确基线应用、人工路径审批、敏感内容排除、确定性指标、来源追溯、时间截断、专项测试与无新增全量失败要求。没有提交、推送或创建 PR。

## 门禁结果

| 门禁 | 结果 | 证据 |
|---|---|---|
| 分支 / HEAD | PASS | `codex/portfolio-tracker` / `25a29f1d2f3c5b19a14d87a0fd72608baabbfccd` |
| 上游同步 | PASS | ahead/behind `0/0` |
| 人工路径审批 | PASS | P2A allowlist 仅含 investment-review 代码、测试、文档、示例与本报告 |
| 敏感内容与大小扫描 | PASS | 构建器通过；数据库、导出、ZIP、环境文件、密钥和大文件未进入补丁 |
| 专项回归 | PASS | `23 passed`（Phase 1 14 + P2A 9） |
| 干净应用 | PASS | 精确 `25a29f1` clean checkout 应用成功 |
| `git diff --check` | PASS | 无错误 |
| 失败集合比较 | PASS | `PASS_NO_NEW_FAILURES`，新增失败 `0` |
| 全量失败集合比较 | PASS_NO_NEW_FAILURES | 候选与基线保留相同 5 个 Bundle 10R 失败，新增失败为 0 |
| 仓库全绿 | NOT_ACHIEVED | 5 个既有失败仍需 Bundle 10R 独立维护补丁 |
| Git 发布 | NOT_RUN | 补丁明确禁止自动提交、推送和 PR |

## 全量测试对比

- `a12cbb8`：`661 passed, 2 skipped, 5 failed`
- 干净 P2A 候选：`684 passed, 2 skipped, 5 failed`
- 新增失败：`0`
- 保留失败：`5`
- 修复失败：`0`

保留失败节点：

1. `tests/test_r5_bundle10_close.py::test_bundle10_completion_and_external_review_lifecycle_passes`
2. `tests/test_r5_bundle10_human_review_finalize.py::test_finalizer_closes_only_a_validated_temp_human_submission`
3. `tests/test_r5_bundle10_human_review_handoff.py::test_bundle10_finalized_human_review_handoff_is_hash_bound`
4. `tests/test_r5_bundle10_human_review_submission.py::test_finalized_human_submission_validates_without_mutating_handoff`
5. `tests/test_r5_bundle10_state_sync.py::test_bundle10_state_is_finalized_after_external_human_review`

这些节点与基线完全相同，属于明确排除的 Bundle 10R 独立维护范围。

## 安全边界复核

- 未修改 portfolio 源数据库或正式 investment-review 旁路库；
- 测试只使用合成数据和临时旁路库；
- 事前快照强制 `observed_at` / `known_at` 不晚于参考事件；
- 事后快照单独放在 `post_event_observation`；
- 负数量、零价格、未知行业和币种未换算不被静默修复；
- 输出不包含买卖建议、仓位指令、机械评分或心理诊断。
