# P2G Stage Three Behavior Hypothesis Loop — Canonical Close Readout

- package_id: `NIGHT-P2G-STAGE3-CLOSE-01`
- functional_close_status: `accepted`
- locked_baseline: `1fc0a472899867e6b51315463596bf3461cd3d3d`
- publication_receipt: `.codex_tmp/P2G_STAGE3_NIGHT_<shortsha>/`
- scope: `P2G-4 immutable review + behavior hypothesis ledger + P2G-1-to-ledger gates`

本回执关闭阶段三的功能边界，不把 Behavior Hypothesis Ledger 命名为 `P2G-5`，也不
启动阶段四干预运行时。最终远端 SHA、GitHub Actions URL、交付 ZIP 和 SHA-256 在发布
完成后写入独立 delivery receipt；它们不是研究 artifact 的第二事实源。

## 状态语义

| 对象 | 可表达的状态 | 本阶段含义 |
|---|---|---|
| P2G-2 observation | observed / not_observed / insufficient_evidence / not_comparable / not_applicable | 确定性 detector 对冻结事实的观察结果，不是解释 |
| P2G-3 candidate | proposed | recorded JSON 生成但尚未人工审核的候选 |
| P2G-4 revision | accepted / rejected / superseded / proposed | accepted 只是人工确认的工作假设；旧状态始终可审计 |
| Behavior Hypothesis Ledger | active / audit | active 只含 accepted occurrence；audit 保留全部状态与 lineage |

任何状态都不构成事实证明、心理诊断、人格画像、机械评分、置信度、交易建议或仓位建议。

## 冻结契约

- `docs/contracts/P2G_4_BEHAVIOR_HYPOTHESIS_REVIEW_REQUEST.schema.json`
- `docs/contracts/P2G_4_BEHAVIOR_HYPOTHESIS_REVISION.schema.json`
- `docs/contracts/P2G_BEHAVIOR_HYPOTHESIS_LEDGER.schema.json`
- `docs/playbooks/INVESTMENT_REVIEW_P2G_4.md`
- `docs/playbooks/INVESTMENT_REVIEW_BEHAVIOR_HYPOTHESIS_LEDGER.md`

P2G-4 请求使用 exact expected parent、actor、UTC reviewed time、非空 reason 和原子化
actions。correct 必须完整替换业务字段、supersede 旧 identity、重新执行 P2G-3
scope/ref/guardrail，并把新 identity 返回 `proposed`。revision 和 ledger 均 create-only。

## CLI inventory

- `behavior-hypothesis-review`
- `behavior-hypothesis-validate`
- `behavior-hypothesis-render`
- `behavior-hypothesis-diff`
- `behavior-hypothesis-revision-list`
- `behavior-hypothesis-ledger-build`
- `behavior-hypothesis-ledger-validate`
- `behavior-hypothesis-ledger-query`
- `behavior-hypothesis-ledger-render`

所有命令均以显式 artifact 为输入。P2G-4 和 ledger 不查询 SQLite、不访问网络、不调用
live model、不读取当前时间，也不解析 `latest` 别名。

## Ledger 关闭结论

- 只消费完整、连续、唯一 latest head 的 P2G-4 revision chains 及其精确 P2G-2 sources。
- 每个 revision 都要离线验证并执行 exact P2G-2 source replay；断链、分叉、循环、重复
  revision、缺失或多余 source 均整包 blocked。
- fingerprint 覆盖完整 canonical hypothesis payload；只允许 exact dedup，不做语义
  合并、相似度聚类、排名、评分或新解释。
- occurrence 保留 source hypothesis/observation content IDs、chain/head、lineage、status
  和 review history；去重不折叠 provenance。
- source replay 从显式 sources 重建整份 ledger，并比较 canonical bytes/content ID。

## 本地门禁实测

| 门禁 | 真实结果 |
|---|---|
| N0 相关基线 | `202 passed` |
| N0 全仓基线 | `1254 passed, 2 skipped` |
| P2G-2/3/4 + ledger 跨阶段回归 | `161 passed` |
| P2G-4 定向 | `24 passed` |
| ledger 定向 | `9 passed` |
| P2G-1→ledger 端到端与失败矩阵 | `16 passed` |
| 全部 `test_investment_review*.py` | `610 passed` |
| N5 全仓门禁 | `1303 passed, 2 skipped` |
| 关键确定性重复门禁 | `3 passed` |

两个 skip 与锁定基线数量一致；本包没有新增 xfail，也没有通过删测、放宽 schema 或降低
护栏修绿。最终文档提交后的本地复核和 GitHub Actions 结果以 delivery receipt 为准。

## Commit checkpoints

- `88d20e2` — P2G-4 contracts
- `167b2a1` — immutable adjudication engine
- `4671e6a` — render/diff/revision audit tools
- `b54ceb2` — deterministic behavior hypothesis ledger
- `b79cbac` — stage-three end-to-end release gates

本回执及导航更新位于独立文档提交；最终提交 SHA 由 publication receipt 冻结。

## Known limitations and next owner

| 项目 | severity | owner | next_step |
|---|---|---|---|
| P2G-5 发布门禁/月度报告运行时未实现 | informational | future P2G package | 另立契约和工作包，不从 ledger 隐式推导 |
| 阶段四 intervention、自动 personal playbook、Web/UI/API 未进入本包 | informational | future approved scope | 需要新的明确授权、证据边界和安全门禁 |
| accepted 仍可能随新证据被 correction/supersede | expected uncertainty | human reviewer | 以新 revision 和 change history 更新，不静默改写 |

当前功能关闭无 blocker。上述项目是明确的范围边界，不伪装为已实现能力。
