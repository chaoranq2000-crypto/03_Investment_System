# P2H Stage 2 Slice A Observation Protocol Contract Decision

## 决定

- 状态：`locked_for_implementation`
- 基线：`a9051cd5996274afaa9386f4e43737ae743aef7c`
- 范围：`observation protocol contract and lifecycle ledger`
- Stage 1 消费方式：只读，不修改 candidate、review event、projection、source artifact 或既有表行。
- 协议创建方式：必须先有人类提交或经人类确认的显式 draft；
  `accepted_for_observation` 不会自动生成或激活 protocol。
- 终态语义：`completed` 和 expiry 只描述协议生命周期，不证明或否定 hypothesis，
  不构成心理诊断、评分、画像或交易建议。

## N0 实时门结果

| 门 | 实测结果 |
|---|---|
| `ls-remote` / remote-tracking | 均为 `a9051cd5996274afaa9386f4e43737ae743aef7c` |
| Actions `29763463924` | `codex/portfolio-tracker` / `a9051cd...` / `success` |
| Stage 1 close readout blob | `83e09f8ac59c33a6a1871a98b4dedb800043cee5` |
| Stage 1 candidate schema blob | `fe59b4e8c18e8d5e6fe2e62ef8a2fcba3135c141` |
| 当前 dirty worktree status | 1635 bytes；SHA-256 `7B8E3F54A5A2A62068A712B6922308C92A659AAB57381900D8433B071F54356D` |
| Stage 1 clean worktree status | 0 bytes；SHA-256 `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855` |
| P2H Stage 1 targeted | `52 passed` |
| investment-review baseline | `662 passed` |
| full repository baseline | `1355 passed, 2 skipped` |

工作分支为 `codex/p2h-stage2-observation-protocol`，隔离 worktree 为
`C:\Projects\03_Investment_System_p2h_stage2_observation`。N0 没有修改 tracked 文件。

## Stage 1 正式读取接口审计

完整输入可以从现有正式接口取得，因此 N1 不触发 blocker：

1. `ReviewStore.get_behavior_hypothesis_candidate(candidate_id)` 返回精确 canonical
   candidate payload。
2. `ReviewStore.list_behavior_hypothesis_review_events(candidate_id=...)` 在不传时间过滤器时
   返回该 candidate 的完整 create-only event set，并按
   `effective_at -> knowledge_at -> reviewed_at -> review_event_id` 排序。
3. `ReviewStore.project_behavior_hypothesis_candidate(..., as_of=...,
   knowledge_cutoff=...)` 从 cutoff 可见事件重放历史 projection。
4. `ReviewStore.replay_behavior_hypothesis_candidate(..., source_artifacts=...)` 对 exact
   source artifact 做 source replay。

Slice A ingest/replay 必须重新调用第 1、2、3、4 项。protocol 绑定完整事件引用及其 canonical
集合哈希；若数据库中完整事件集与绑定集合不完全相同，必须以
`STAGE1_REVIEW_EVENT_SET_MISMATCH` 失败。不得以 latest status、手工摘要或只传 cutoff
可见事件代替完整集合。

## 三对象契约

| 对象 | 身份与输入 | 核心约束 |
|---|---|---|
| `p2h.observation_protocol.v1` | content-derived `protocol_id` / `canonical_hash`；绑定 exact candidate/hash、source refs、完整 event refs/set hash、accepted projection/hash | 显式 draft；UTC whole-second 双时间；固定 observation window、checkpoints、expiry、事实规格、适用/反证/停止条件、missing policy、privacy scope |
| `p2h.observation_protocol_review_event.v1` | content-derived event ID/hash；绑定 protocol | 仅 `submitted`、`approved_for_observation`、`activated`、`paused`、`completed`、`abandoned`、`superseded`、`note_added`；人工 reviewer 与理由必填；create-only |
| `p2h.observation_protocol_projection.v1` | 从 exact protocol 与完整 event set 在显式 `as_of` / `knowledge_cutoff` 下重放 | 仅生命周期状态；事件乱序不改变 bytes；同语义时点冲突、孤儿、非法跃迁、错误 supersession fail closed |

accepted projection 必须由完整 Stage 1 event set 在协议声明的两个 cutoff 上重新计算，状态
精确等于 `accepted_for_observation`。protocol builder 不能接收一个未验证的布尔值替代该投影。

## 存储决定

- 继续使用 investment-review v2 sidecar，幂等增加 feature schema
  `p2h_stage2_slice_a_schema_version=1`。
- 新表仅为 `behavior_observation_protocols` 与
  `behavior_observation_protocol_review_events`。
- protocol/event 相同 ID、相同 canonical payload 重放返回 `SKIPPED`；同 ID、不同 payload
  或同 hash、不同 owner 显式冲突。
- 公共 API 只提供 insert/get/list/project/replay，不提供 update/delete。
- Stage 1 表仅通过正式方法读取；不写 portfolio SQLite，不读取 broker export 或凭证。

## 生命周期矩阵

| 当前状态 | 允许的状态事件 |
|---|---|
| `draft` | `submitted` |
| `submitted` | `approved_for_observation`, `abandoned`, `superseded` |
| `approved_for_observation` | `activated`, `abandoned`, `superseded` |
| `active` | `paused`, `completed`, `abandoned`, `superseded` |
| `paused` | `activated`, `completed`, `abandoned`, `superseded` |
| `completed` | `superseded` |
| `abandoned` | `superseded` |
| `superseded` | 无 |

`note_added` 只在 protocol 已提交后允许且不改变状态。expiry 单独投影为
`not_expired` / `expired`，不自动制造 `completed`；过期后不能批准、激活或暂停，但允许用人工
事件关闭或 supersede 历史协议。

## 精确 changed-file allowlist

以下 20 个非 glob 路径是本切片唯一允许变化的 tracked 文件；N6 必须要求实际 changed path
集合与本表完全一致：

1. `.agents/skills/investment-review/SKILL.md`
2. `README.md`
3. `docs/index.md`
4. `docs/contracts/P2H_STAGE2_OBSERVATION_PROTOCOL.schema.json`
5. `docs/contracts/P2H_STAGE2_OBSERVATION_PROTOCOL_REVIEW_EVENT.schema.json`
6. `docs/contracts/P2H_STAGE2_OBSERVATION_PROTOCOL_PROJECTION.schema.json`
7. `docs/plans/P2H_STAGE2_OBSERVATION_PROTOCOL_CONTRACT_DECISION.md`
8. `docs/playbooks/INVESTMENT_REVIEW_P2H_STAGE2_OBSERVATION_PROTOCOL.md`
9. `reports/investment_review/p2h_stage2/P2H_STAGE2_SLICE_A_CLOSE_READOUT.md`
10. `src/investment_review/behavior_observation_protocols.py`
11. `src/investment_review/store.py`
12. `src/investment_review/cli.py`
13. `tests/test_investment_review_p2h_stage2_contract.py`
14. `tests/test_investment_review_p2h_stage2_validation.py`
15. `tests/test_investment_review_p2h_stage2_store.py`
16. `tests/test_investment_review_p2h_stage2_lifecycle.py`
17. `tests/test_investment_review_p2h_stage2_e2e.py`
18. `tests/test_investment_review_p2h_stage2_guardrails.py`
19. `tests/fixtures/investment_review_p2h_stage2/README.md`
20. `tests/fixtures/investment_review_p2h_stage2/protocol_draft.json`

## 硬停止与 backflow

- Stage 1 完整 event set 接口或历史 projection 无法复现：停止，不新造 Stage 1 接口副本。
- 需要改动 Stage 1 schema/payload/event/table row：停止，回流 Stage 1 单独修订。
- exact event set、candidate hash、source replay 或 projection hash 漂移：停止，输出 blocker。
- 需要读取真实 portfolio SQLite、broker export、凭证或个人原始数据：停止。
- 需要 intervention/experiment action、attempt/outcome、profile/PersonalPlaybook、UI/Web/API、
  交易建议或 Slice B 内容：停止并要求独立授权。
- 实际 changed path 离开上述 20 个文件或文件数超过 24：停止。
- 远端推进、CI/确定性/source/tamper/全仓测试失败，或两个源工作区 status hash 改变：停止，
  不放宽门禁、不 force push。
