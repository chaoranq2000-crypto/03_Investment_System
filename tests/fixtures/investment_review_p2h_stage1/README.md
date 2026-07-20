# P2H Stage 1 synthetic fixtures

这些文件只包含虚构 cohort、evaluation 和 reviewer 标识，不包含真实持仓、成交、证券代码、
账户或身份数据。

- `synthetic_observation_source.json`：最小 source-replay fixture。
- `candidate_draft.json`：可由 `behavior-candidate-build` 构建的候选提交。

人工复核事件在测试中根据构建后的确定性 `candidate_id` 生成，避免以 `latest` 或人工占位 ID
绕过绑定。
