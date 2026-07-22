# P2H Stage 2 Slice A Observation Protocol and Lifecycle Ledger — Canonical Close Readout

- package: `P2H_STAGE2_NEXT_TASK_PLANNING_PACKAGE_a9051cd_20260722`
- local_functional_close_status: `accepted`
- locked_baseline: `a9051cd5996274afaa9386f4e43737ae743aef7c`
- target_branch: `origin/codex/portfolio-tracker`
- implementation_branch: `codex/p2h-stage2-observation-protocol`
- scope: `observation protocol contract and lifecycle ledger`

本回执关闭 P2H Stage 2 Slice A 的本地功能与回归门禁。包含本文件的 N6 提交、最终远端
SHA、该 SHA 对应的 GitHub Actions run、交付 ZIP 与 SHA-256 由
`.codex_tmp/P2H_STAGE2_SLICE_A_<shortsha>/P2H_STAGE2_SLICE_A_COMPLETION_READOUT.md`
冻结；这些发布字段不能在不改变自身 SHA 的前提下写回本提交，因此不制造第七个回填提交。

## N0 实时锚点

- 开工时 `ls-remote` 与 remote-tracking SHA 均为
  `a9051cd5996274afaa9386f4e43737ae743aef7c`。
- Actions run `29763463924` 的 head branch 为 `codex/portfolio-tracker`，head SHA 与基线
  相同，conclusion 为 `success`。
- Stage 1 close readout Git blob：`83e09f8ac59c33a6a1871a98b4dedb800043cee5`。
- Stage 1 candidate schema Git blob：`fe59b4e8c18e8d5e6fe2e62ef8a2fcba3135c141`。
- 基线门：P2H Stage 1 `52 passed`；investment-review `662 passed`；全仓
  `1355 passed, 2 skipped`。

## Canonical 合成验收输入

- candidate ID：`candidate:c63b8f4bef821c6cfaafe0da04140086`
- candidate hash：
  `sha256:c63b8f4bef821c6cfaafe0da0414008656d19c8760a674a096d8678af7de330e`
- complete Stage 1 review event IDs：
  `review_event:d798fec849f1be0baf62621689aeed24`、
  `review_event:9671ef10324dbb1b95f04662ec32d894`
- review event set hash：
  `sha256:a71d5fa0644c52b8b5fd4605ce31147c08fcd5b5038ff891b23bb21dcd718430`
- accepted projection：`as_of=2026-07-20T14:00:00Z`、
  `knowledge_cutoff=2026-07-20T14:00:00Z`、status
  `accepted_for_observation`
- projection hash：
  `sha256:eb864d24487e16a8693896fdbebcbae95e76e3a012ed31b639699def4ed2e1a5`
- protocol ID：`protocol:18c002d071ba52139a373e5ef0b14cfe`
- protocol hash：
  `sha256:18c002d071ba52139a373e5ef0b14cfe67c1f35097485e5320748310baa3840b`
- Stage 1 source replay：`verified`

这些标识只来自 checked-in synthetic fixtures 和固定人工事件；未读取真实 portfolio
SQLite、broker export、账户、持仓、成交或凭证。

## 已交付能力

Slice A 新增三层彼此分离的对象：

1. `p2h.observation_protocol.v1`：显式、经人工确认的 protocol，绑定 exact Stage 1
   candidate/source/完整 event set/accepted historical projection；
2. `p2h.observation_protocol_review_event.v1`：create-only 人工生命周期事件；
3. `p2h.observation_protocol_projection.v1`：按 `as_of` 与 `knowledge_cutoff` 重放的
   governance-only 状态与独立 expiry state。

protocol 固定 required-fact keys、observation window、review checkpoints、applicability、
disconfirming、stop、expiry、missing-evidence policy 与 privacy scope。identity/hash 来自
canonical payload；集合型 refs 稳定排序，语义列表保序；所有时间为 UTC whole seconds。
builder 不读取系统当前时间，不写绝对路径、用户名或机器名。

sidecar 在 schema v2 上幂等增加 `p2h_stage2_slice_a_schema_version=1` 与两个 feature
table。protocol/event 相同 ID、相同 payload 重放返回 `SKIPPED`；同 ID 内容漂移显式冲突；
公开 API 不存在 update/delete。Stage 1 candidate/event 行与 source artifacts 保持只读。

事件按 `effective_at -> knowledge_at -> reviewed_at -> protocol_review_event_id` 投影。
输入乱序与完全相同的重复事件不改变 projection bytes；同一前三项的多个状态事件显式
`CONCURRENT_PROTOCOL_STATE_EVENTS`。`note_added` 不改变状态，future knowledge 不进入历史
投影，expiry 不自动生成 `completed`。

## Lifecycle 与 CLI

状态为 `draft`、`submitted`、`approved_for_observation`、`active`、`paused`、
`completed`、`abandoned`、`superseded`。`completed` 与 `expired` 都只描述协议治理，
不证明或否定 hypothesis。

CLI inventory：

- `observation-protocol-build`
- `observation-protocol-validate`
- `observation-protocol-ingest`
- `observation-protocol-event-record`
- `observation-protocol-list`
- `observation-protocol-show`
- `observation-protocol-status`
- `observation-protocol-replay`

成功退出码为 `0`；blocked、conflict、create-only 输出已存在或其他契约失败为 `2`。错误
输出不回显完整 protocol/candidate payload。

## Commit checkpoints

| 卡片 | 提交 | 内容 |
|---|---|---|
| N1 | `9d3efac` | entry contract、Stage 1 正式接口审计与 20-file exact allowlist |
| N2 | `191c8c0` | 三 schema、canonical builder/validator 与 Stage 1 source replay |
| N3 | `3206eef` | v2 sidecar additive schema 与 create-only protocol/event persistence |
| N4 | `9897794` | 人工生命周期账本、双时间 projection、expiry 与严格冲突门 |
| N5 | `fe8ea8e` | 8 个 CLI、synthetic fixture、E2E、hostile guardrails 与 playbook |
| N6 | `this commit` | skill/README/docs 导航、全量回归与关闭回执 |

## 本地验收实测

| 门禁 | 结果 |
|---|---|
| P2H Stage 2 Slice A targeted（6 files） | `46 passed` |
| P2H Stage 1 regression（6 files） | `52 passed` |
| 全部 investment-review（32 files） | `708 passed` |
| 全仓 | `1401 passed, 2 skipped` |
| Python compile | 通过 |
| `git diff --check` | 通过 |

相对基线净增 46 个通过测试，0 failure、0 error；没有新增 skip/xfail/xpass，没有删测、
放宽 Stage 1 schema、修改既有 golden/hash 或升级依赖。

## Safety 与负向证明

- direct buy/sell/hold、position sizing、expected return：0；
- mechanical score、rank、grade、numeric confidence：0；
- psychology/personality diagnosis、profile/PersonalPlaybook write：0；
- intervention/experiment action、attempt/outcome：0；
- portfolio SQLite、broker、credential access：0；
- Stage 1 schema/row/source mutation：0；
- UI/Web/API/order execution changes：0。

负向矩阵覆盖 candidate/source/event/projection/hash drift、future knowledge、绝对路径、未知
字段、advice、score、numeric confidence、diagnosis、profile、intervention、overwrite、孤儿、
非法跃迁、同语义时点冲突、错误 supersession 与 expiry 后非法状态事件。checked-in fixture
只含 `synthetic-*` 标识。

## Git 与工作区保护

- exact changed paths：20，等于 N1 allowlist，低于 24-file 上限；
- merge commits：0；checkpoint commits：恰好 6（N1–N6 各 1）；
- 当前用户 dirty worktree status bytes：1635；before/close-check SHA-256 均为
  `7B8E3F54A5A2A62068A712B6922308C92A659AAB57381900D8433B071F54356D`；
- Stage 1 clean worktree status bytes：0；before/close-check SHA-256 均为
  `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`；
- 未 stash、clean、reset、rebase、amend、force push 或修改 `.github/workflows/**`。

## 发布验证与暂停点

最终 push 前必须再次 fetch 并要求远端仍为锁定基线。只允许普通 fast-forward push，不
force push，不创建 PR。final SHA、Actions run/conclusion、exact changed-file/hash manifest、
delivery ZIP/hash、禁入项和两个源工作区最终 hash 写入外部 completion receipt。

Slice B intervention/experiment proposal governance、attempt/outcome ledger、
profile/PersonalPlaybook、UI/Web/API 与真实数据运行均未启动。完成 final-SHA CI 与 delivery
后停止，不顺手进入下一切片。
