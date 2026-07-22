# Investment Review P2H Stage 2 Slice A 操作手册

## 边界

Slice A 把一个已经由人工复核为 `accepted_for_observation` 的 P2H Stage 1 candidate，转换为
显式提交、可审计、可按双时间重放的 observation protocol。它只管理观察协议及人工生命周期
事件，不判断 hypothesis 真伪。

本切片不生成或执行 intervention/experiment action，不记录 attempt/outcome，不写
profile/PersonalPlaybook，不连接 UI/Web/API，不读取 portfolio SQLite、broker export 或凭证，
也不输出买卖、仓位、收益、评分或数值置信度。

`completed` 只表示协议生命周期结束；expiry 只表示观察期限已到。二者都不等于
`proven_true`、`proven_false`、心理诊断或交易建议。

## 数据流

```text
exact Stage 1 candidate + exact source artifacts
  + complete Stage 1 review event set
  + accepted historical projection(as_of, knowledge_cutoff)
  + explicit human-confirmed protocol draft
  -> canonical protocol build / offline validate / source replay
  -> create-only v2 sidecar protocol
  -> immutable human lifecycle events
  -> historical protocol projection(as_of, knowledge_cutoff)
```

protocol builder 不接受一个布尔值替代 Stage 1 acceptance。它必须用完整事件集重新计算历史
projection，并要求状态精确为 `accepted_for_observation`。sidecar ingest/replay 会再次从 Stage 1
正式 store 接口取得 candidate 和完整 event set，任何集合、hash 或 projection 漂移都失败。

## 合成 fixture

本仓库只提供虚构标识：

```text
tests/fixtures/investment_review_p2h_stage1/candidate_draft.json
tests/fixtures/investment_review_p2h_stage1/synthetic_observation_source.json
tests/fixtures/investment_review_p2h_stage2/protocol_draft.json
```

先按 Stage 1 手册生成 canonical candidate 与 `submitted`、
`accepted_for_observation` 两个 canonical review event JSON。以下示例假定它们位于
`.codex_tmp/`，且数据库是单独的 synthetic sidecar；不得把 portfolio 数据库传给 `--db`。

## Build 与离线校验

```powershell
python -m src.investment_review observation-protocol-build `
  --input tests/fixtures/investment_review_p2h_stage2/protocol_draft.json `
  --candidate-artifact .codex_tmp/p2h_candidate.json `
  --review-event .codex_tmp/p2h_candidate_submitted.json `
  --review-event .codex_tmp/p2h_candidate_accepted.json `
  --candidate-source-artifact tests/fixtures/investment_review_p2h_stage1/synthetic_observation_source.json `
  --output .codex_tmp/p2h_observation_protocol.json

python -m src.investment_review observation-protocol-validate `
  .codex_tmp/p2h_observation_protocol.json
```

输出路径必须尚不存在。builder 不读取系统当前时间；`created_at`、`effective_at`、
`knowledge_at`、accepted projection cutoffs、窗口、checkpoints 与 expiry 均来自显式 draft，
并规范化为 UTC whole seconds。

## Exact Stage 1 source replay

```powershell
python -m src.investment_review observation-protocol-validate `
  .codex_tmp/p2h_observation_protocol.json `
  --source-replay `
  --candidate-artifact .codex_tmp/p2h_candidate.json `
  --review-event .codex_tmp/p2h_candidate_submitted.json `
  --review-event .codex_tmp/p2h_candidate_accepted.json `
  --candidate-source-artifact tests/fixtures/investment_review_p2h_stage1/synthetic_observation_source.json
```

source replay 同时复核：

- candidate ID 与 canonical hash；
- exact source artifact content ID 和 source locator；
- 完整 Stage 1 review event refs 与集合 hash；
- 声明 `as_of` / `knowledge_cutoff` 下的 accepted projection bytes/hash；
- protocol 自身 identity、时间、privacy、missing-state 与 no-advice/no-score 边界。

## 初始化与 create-only ingest

```powershell
python -m src.investment_review `
  --db .codex_tmp/p2h_stage2_review.sqlite3 `
  init

python -m src.investment_review `
  --db .codex_tmp/p2h_stage2_review.sqlite3 `
  observation-protocol-ingest .codex_tmp/p2h_observation_protocol.json `
  --candidate-source-artifact tests/fixtures/investment_review_p2h_stage1/synthetic_observation_source.json
```

protocol 对 Stage 1 candidate/event 表只读。相同 ID、相同 canonical payload 重放返回
`SKIPPED`；同 ID、不同 payload 返回 conflict，不能覆盖。公开 API 没有 update/delete。

## 人工生命周期事件

事件输入必须由人工提交，并包含 pseudonymous `reviewer_ref`、rationale、effective/knowledge/
reviewed time、evidence cutoff 与显式 supersession refs。例如：

```json
{
  "protocol_id": "protocol:<exact-content-derived-id>",
  "event_type": "submitted",
  "reviewed_at": "2026-07-20T16:00:00Z",
  "effective_at": "2026-07-20T16:00:00Z",
  "knowledge_at": "2026-07-20T16:00:00Z",
  "reviewer_ref": "synthetic-human-reviewer",
  "rationale": "The explicit protocol is submitted for human review.",
  "evidence_cutoff": "2026-07-20T15:00:00Z",
  "supersedes_event_id": null,
  "superseded_by_protocol_id": null,
  "provenance": {
    "submitter_kind": "human",
    "source_locator": "synthetic/protocol_submitted.json",
    "tool_version": "p2h.observation_protocol_review_event.builder.v1"
  }
}
```

记录事件：

```powershell
python -m src.investment_review `
  --db .codex_tmp/p2h_stage2_review.sqlite3 `
  observation-protocol-event-record `
  --input .codex_tmp/p2h_protocol_submitted_event.json
```

允许事件为 `submitted`、`approved_for_observation`、`activated`、`paused`、`completed`、
`abandoned`、`superseded`、`note_added`。`note_added` 不改变状态。事件允许乱序导入，但完整
ledger 投影必须满足封闭 transition matrix；同一 semantic time 的多个状态事件会被拒绝。

## 查询、状态与重放

```powershell
python -m src.investment_review `
  --db .codex_tmp/p2h_stage2_review.sqlite3 `
  observation-protocol-list `
  --status active `
  --as-of 2026-07-20T18:00:00Z `
  --knowledge-cutoff 2026-07-20T18:00:00Z

python -m src.investment_review `
  --db .codex_tmp/p2h_stage2_review.sqlite3 `
  observation-protocol-show protocol:<exact-content-derived-id>

python -m src.investment_review `
  --db .codex_tmp/p2h_stage2_review.sqlite3 `
  observation-protocol-status protocol:<exact-content-derived-id> `
  --as-of 2026-07-20T20:00:00Z `
  --knowledge-cutoff 2026-07-20T20:00:00Z

python -m src.investment_review `
  --db .codex_tmp/p2h_stage2_review.sqlite3 `
  observation-protocol-replay protocol:<exact-content-derived-id> `
  --candidate-source-artifact tests/fixtures/investment_review_p2h_stage1/synthetic_observation_source.json
```

`as_of` 控制业务有效时间，`knowledge_cutoff` 控制当时可知范围。事件按
`effective_at -> knowledge_at -> reviewed_at -> protocol_review_event_id` 排序。ID 只作为最后
稳定顺序，不会掩盖同一前三项的状态冲突。expiry 单独投影为 `not_expired` / `expired`，不会
自动制造 `completed`。

## 常见失败码

| code | 含义 |
|---|---|
| `PROTOCOL_SCHEMA_INVALID` / `PROTOCOL_SEMANTIC_INVALID` | protocol 不符合封闭 schema 或时间/治理约束 |
| `PROTOCOL_ID_MISMATCH` / `PROTOCOL_HASH_MISMATCH` | identity 与 canonical content 不一致 |
| `STAGE1_CANDIDATE_HASH_MISMATCH` | exact candidate 已漂移 |
| `STAGE1_SOURCE_REPLAY_FAILED` / `STAGE1_SOURCE_SET_MISMATCH` | source artifact 无法重放或集合不同 |
| `STAGE1_REVIEW_EVENT_SET_MISMATCH` | 完整 Stage 1 event set 与绑定集合不同 |
| `STAGE1_PROJECTION_MISMATCH` | historical accepted projection 不一致 |
| `INVALID_PROTOCOL_TRANSITION` | 生命周期跃迁不在封闭矩阵内 |
| `CONCURRENT_PROTOCOL_STATE_EVENTS` | 同一 semantic time 有多个状态事件 |
| `ORPHAN_PROTOCOL_REVIEW_EVENT` | event 指向另一 protocol |
| `PROTOCOL_SUPERSESSION_EVENT_NOT_VISIBLE` | supersession 未引用更早可见事件 |
| `PROTOCOL_EXPIRED` | expiry 后尝试批准、激活或暂停 |
| `POLICY_DIRECT_ADVICE` / `POLICY_MECHANICAL_SCORE` | 出现建议或机械评分 |
| `POLICY_NUMERIC_CONFIDENCE` / `POLICY_PSYCHOLOGY_DIAGNOSIS` | 出现数值置信度或心理诊断 |
| `POLICY_PROFILE_WRITE` / `POLICY_INTERVENTION_ACTION` | 越过 profile 或 Slice B 边界 |

成功退出码为 `0`；blocked、conflict、create-only 输出已存在或其他契约失败返回 `2`。错误
输出不回显完整 protocol/candidate 私密内容。

## 暂停点

完成 protocol、人工 lifecycle events、双时间查询与 source replay 后停止。Slice B 的
intervention/experiment proposal、attempt/outcome ledger、profile/PersonalPlaybook、
UI/Web/API 和真实数据运行均未启动，也不得从任何 accepted/active/completed 状态自动触发。
