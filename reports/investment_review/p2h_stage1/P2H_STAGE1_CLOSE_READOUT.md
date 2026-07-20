# P2H Stage 1 Behavior Hypothesis Candidate and Review Ledger — Canonical Close Readout

- package: `P2H_STAGE1_NIGHT_WORK_PACKAGE_a1a4fe2`
- local_functional_close_status: `accepted`
- locked_baseline: `a1a4fe2b43d0d624bb41c3524314e483f43c4d4c`
- target_branch: `origin/codex/portfolio-tracker`
- implementation_branch: `codex/p2h-stage1-night`
- scope: `evidence-bound candidate + immutable human review ledger + dual-time projection`

本回执关闭 P2H Stage 1 的本地功能与回归门禁。包含本文件的 N6 提交、最终远端 SHA、
该 SHA 对应的 GitHub Actions run、交付 ZIP 与 SHA-256 由
`.codex_tmp/P2H_STAGE1_NIGHT_<shortsha>/P2H_STAGE1_COMPLETION_READOUT.md` 冻结；这些发布字段
不能在不改变自身 SHA 的前提下写回本提交，因此不在 Git 历史中制造第七个“回填”提交。

## 实现边界

P2H Stage 1 新增三层彼此分离的对象：

1. `p2h.behavior_hypothesis_candidate.v1`：显式提交、绑定 exact source 的候选解释；
2. `p2h.behavior_hypothesis_review_event.v1`：create-only 人工复核事件；
3. `p2h.behavior_hypothesis_projection.v1`：按 `as_of` 与 `knowledge_cutoff` 重放的状态。

`accepted_for_observation` 只表示证据足以支持继续观察，不表示行为原因已经被证明，
不构成心理诊断或交易建议。候选、事件和投影没有 profile、PersonalPlaybook、intervention、
execution、position、return、score 或 confidence percentage 写入字段。

## 契约与实现

- Candidate schema：`docs/contracts/P2H_STAGE1_BEHAVIOR_HYPOTHESIS_CANDIDATE.schema.json`
- Review event schema：`docs/contracts/P2H_STAGE1_BEHAVIOR_HYPOTHESIS_REVIEW_EVENT.schema.json`
- Projection schema：`docs/contracts/P2H_STAGE1_BEHAVIOR_HYPOTHESIS_PROJECTION.schema.json`
- Builder / validator / projector：`src/investment_review/behavior_hypothesis_candidates.py`
- Sidecar store / query：`src/investment_review/store.py`
- CLI：`src/investment_review/cli.py`
- Playbook：`docs/playbooks/INVESTMENT_REVIEW_P2H_STAGE1.md`
- Synthetic fixtures：`tests/fixtures/investment_review_p2h_stage1/`

Candidate ID/hash 来自 canonical payload；集合型 evidence/scope refs 稳定排序，
alternative explanations、applicability、disconfirming observations 与 observation-plan
required facts 保留语义顺序。所有时间规范化为 UTC whole seconds。source replay 要求 exact
artifact content hash、唯一 artifact ID、P2G 自身 validator、`ready` 与 `verified` 状态。

Sidecar 在既有 schema v2 上幂等增加 P2H feature tables，不另建数据库框架，也不访问
portfolio SQLite。相同 ID/payload 重放返回 `SKIPPED`；同 ID 内容漂移显式冲突。公开 API
不存在 update/delete 路径。

事件按 `effective_at -> knowledge_at -> reviewed_at -> review_event_id` 投影。ID 只作为最终
稳定顺序；同一前三项出现多个状态变更会 `CONCURRENT_STATE_EVENTS`，不能被 tie-break
掩盖。乱序写入在完整事件集上得到相同 bytes；历史 accepted/superseded 状态可按双时间
重放。

## CLI inventory

- `behavior-candidate-build`
- `behavior-candidate-validate`
- `behavior-candidate-ingest`
- `behavior-candidate-list`
- `behavior-candidate-show`
- `behavior-review-event-record`
- `behavior-candidate-status`
- `behavior-candidate-replay`

成功退出码为 `0`；blocked、冲突、create-only 路径已存在或其他契约失败为 `2`。错误输出
不回显完整 candidate payload。

## Commit checkpoints

| 卡片 | 提交 | 内容 |
|---|---|---|
| N1 | `e120c9e` | candidate/review-event/projection 领域契约与 schema |
| N2 | `5964041` | canonicalization、ID/hash、validator 与 source replay |
| N3 | `b9bf7b7` | v2 sidecar create-only 存储、查询与重放 |
| N4 | `4122cb8` | 不可变人工事件账本与严格双时间投影 |
| N5 | `3bf8926` | CLI、合成 fixture、playbook 与 P2G→P2H E2E |
| N6 | `this commit` | 负向矩阵、导航、skill、全仓回归与关闭回执 |

## 本地验收实测

| 门禁 | 结果 |
|---|---|
| N0 锁定基线 | `1303 passed, 2 skipped` |
| P2H N1–N6 定向 | `52 passed` |
| 全部 investment-review（26 files） | `662 passed` |
| 全仓 | `1355 passed, 2 skipped` |
| Python compile | 通过 |
| `git diff --check` | 通过 |

全仓相对基线净增 52 个通过测试，0 failure；没有新增 skip/xfail，没有删测、放宽 schema、
修改既有 golden/hash 或升级依赖。

## 负向与数据边界证明

- `tests/test_investment_review_p2h_stage1_guardrails.py` 覆盖 advice、execution、position、
  expected return、score、numeric confidence、profile/playbook/intervention 字段拒绝。
- 缺 alternative explanation、同时缺 counterevidence/source gap、future knowledge、hash
  mismatch、ambiguous ref、孤儿事件、非法跃迁和并发状态事件均 fail closed。
- 无事件的 candidate 仍是 `candidate`；不能自动进入 observing，也不存在 `proven_true`。
- E2E 使用既有合成 P2G-2 artifact；运行前后 source 文件 SHA-256 一致。
- checked-in fixture 只含 `synthetic-*` 标识，不含真实账户、持仓、成交、证券代码或身份数据。
- 本阶段没有数据库文件、ZIP、环境目录、缓存、测试输出或原工作区脏文件进入 Git。

## 发布验证

- 已确认基线 Actions run：
  `https://github.com/chaoranq2000-crypto/03_Investment_System/actions/runs/29683070893`
  （`success`，head `a1a4fe2b43d0d624bb41c3524314e483f43c4d4c`）。
- 最终 push 前必须再次 fetch，并要求远端仍为锁定基线。
- 仅允许普通 fast-forward push；不 force push，不创建 PR。
- 新 target SHA 的 Actions URL、status、conclusion 和 CI SHA 写入 completion receipt。

## 已知限制与暂停点

| 项目 | severity | owner | next_step |
|---|---|---|---|
| intervention / experiment / improvement plan 未实现 | informational | future P2H Stage 2 package | 需要新的明确契约和授权 |
| profile / PersonalPlaybook 自动更新未实现 | informational | future approved scope | 不从 accepted 状态隐式触发 |
| UI/Web/API 与自动模型生成未实现 | informational | future approved scope | 另立安全边界和工作包 |

当前 P2H Stage 1 本地功能关闭无 blocker。完成发布、目标 SHA CI 与交付包校验后停止，
不得顺手进入 Stage 2。
