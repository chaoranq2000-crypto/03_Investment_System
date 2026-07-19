# Investment Review P2G-4 操作手册

P2G-4 对一份已经通过离线验证和 P2G-2 source replay 的
`p2g.behavior_hypothesis_set.v1` 候选集执行人工 `accept`、`reject` 或
`correct`。每次请求生成新的 `p2g.behavior_hypothesis_revision.v1`，不覆盖
P2G-3 artifact 或任何旧 revision。

`accepted` 只表示人工确认可保留为工作假设，不表示客观事实、统计证明、心理诊断
或交易建议。

## 阶段边界

- 输入只能是显式传入的 P2G-3 candidate set 或其 P2G-4 revision、review request
  和精确 P2G-2 observation artifact。
- 不读取或写入 SQLite，不读取网络，不调用模型，不使用当前时间。
- 不修改 P2G-1/P2G-2/P2G-3 artifact、model attempt 或历史 revision。
- 不进入 intervention、自动 personal playbook、Web/UI、API 或阶段四运行时。
- 所有 action 先完整预检；任一 action 失败时整个请求失败，不生成部分 revision。

## 请求契约

规范 schema：

```text
docs/contracts/P2G_4_BEHAVIOR_HYPOTHESIS_REVIEW_REQUEST.schema.json
```

请求必须包含：

- `request_id`：对规范化请求（排除 `request_id`）计算 SHA-256 后取前 32 位，格式为
  `review-request:<32-hex>`；
- `expected_parent_content_id`：必须精确等于当前输入 artifact 的 `content_id`；
- `actor`、规范 UTC 整秒 `reviewed_at`；
- 一个或多个 action；每个 action 有唯一 `target_hypothesis_id`、canonical action、
  非空 `reason` 和显式 `replacement`。

`accept` / `reject` 的 `replacement` 必须为 `null`。`correct` 必须提供完整 replacement，
列出以下全部业务字段，不允许隐式 merge：

- `statement`
- `scope`
- `evaluation_refs`
- `supporting_reasons`
- `counterevidence_evaluation_refs`
- `counterevidence_search`
- `alternative_explanations`
- `assumptions`
- `uncertainty_notes`
- `falsification_conditions`
- `next_observations_needed`
- `temporal_perspective`

请求示意：

```json
{
  "schema_version": "p2g.behavior_hypothesis_review_request.v1",
  "request_id": "review-request:00000000000000000000000000000000",
  "expected_parent_content_id": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "actor": "reviewer:example",
  "reviewed_at": "2026-07-19T12:00:00Z",
  "actions": [
    {
      "target_hypothesis_id": "hypothesis:00000000000000000000000000000000",
      "action": "accept",
      "reason": "已核对冻结 evaluation、反证和适用范围。",
      "replacement": null
    }
  ]
}
```

示例 ID 仅展示格式；实际请求必须使用内容派生 ID。

## 状态机

```text
proposed --accept--> accepted
proposed --reject--> rejected
proposed --correct--> superseded + new proposed
accepted --correct--> superseded + new proposed
rejected --correct--> superseded + new proposed
superseded ----------> terminal
```

- `accept` / `reject` 只允许作用于 `proposed`。
- 对已经接受或拒绝的工作假设，只有显式 `correct` 可以建立后续候选；旧项进入
  `superseded`，新项回到 `proposed`，必须再次独立 accept/reject。
- `correct` 生成新的内容派生 hypothesis ID，并记录
  `lineage_root_hypothesis_id` 与 `supersedes_hypothesis_id`。
- accept/reject 不改变 hypothesis identity，只在新 revision 中改变其审计状态。
- superseded 项永不删除，也不能再次成为 action target。

## Revision 契约

规范 schema：

```text
docs/contracts/P2G_4_BEHAVIOR_HYPOTHESIS_REVISION.schema.json
```

每个 revision 保存：

- 唯一 `revision_chain_id`、连续 `revision_no`、立即父 `parent_content_id` 和根
  P2G-3 content ID；
- P2G-3 hypothesis-set、P2G-2 observation-set、evaluation inventory 和模型
  provenance 绑定；
- 完整 hypothesis audit view；
- append-only review events，包括 request、actor、reason、reviewed time、target/result
  IDs 和前后状态；
- source replay、release readiness 和 canonicalization 元数据。

revision artifact 本身就是审核回执，不再创建第二个功能重叠的 receipt 事实源。

## Canonicalization 和不可变性

- 所有 timestamp 规范为 UTC `Z` 整秒。
- action 按 `target_hypothesis_id` 排序；同一 target 在一个请求中只能出现一次。
- string-set 字段排序去重；evaluation inventory 按 `evaluation_id` 排序；hypothesis
  按 `hypothesis_id` 排序；review event 按 `reviewed_at`、`review_event_id` 排序。
- `request_id` 对排除自身后的规范请求内容派生。
- `content_id` 对排除自身后的完整 revision 内容派生。
- `revision_chain_id` 只由根 P2G-3 content ID 派生。
- 输出使用 create-only；已存在路径不得覆盖。

## 校验和 source replay

离线校验必须检查 schema、规范顺序、ID/hash、状态机、event prefix、父链和冻结
provenance。source replay 还必须用精确 P2G-2 artifact：

1. 重放 P2G-3 evaluation inventory 和 scope 绑定；
2. 重新校验所有保留及 correction 新生成 hypothesis 的 evaluation refs、scope、
   counterevidence 和 P2G-3 护栏；
3. 拒绝 source tamper、scope/ref mismatch、心理诊断、评分、交易建议、事后最佳价、
   无证据单 episode 动机推断或未受限的长期结论。

计划 CLI（N2/N3 实现）：

```powershell
python -m src.investment_review behavior-hypothesis-review `
  --artifact <p2g3-or-current-revision.json> `
  --request <review-request.json> `
  --observation-artifact <p2g2-observations.json> `
  --output <new-revision.json>

python -m src.investment_review behavior-hypothesis-validate `
  <revision.json> --source-replay `
  --observation-artifact <p2g2-observations.json>
```

validate、render、diff 和 revision-list 只审查 artifact，不产生新解释。
