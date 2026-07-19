# ExecPlan — Night03

本文件是活文档。执行过程中必须持续更新 `Progress`、`Discoveries`、
`Decisions` 和 `Remaining work`，不能先写计划后宣布完成。

## Objective

在 `codex/r5-night03-targeted-backflow-intake` 上实现决定摄取、occurrence 状态转换、批准 pointer
分波执行、候选包升级、dependency 解锁与可信 blocker 账本，并完成全量回归、推送和晨报。

## Phase A — Baseline and queue import

- 硬核验 `069da527452def6c59c3772750e933d8611ccadf`、Night02 物理收据、CI、PR、clean；
- 建立 Night02 输入 SHA 清单；
- 只读导入 69 项队列；
- 核对 63 + 6 与五类分布；
- 固化 0/63 与 Goal open。

## Phase B — Decision intake

- 建立四类决定 schema；
- exact-hash、authority、reviewer identity 校验；
- evidence/analysis/human/pointer adapters；
- 候选与解决状态不可混淆。

## Phase C — Resolution engine

- occurrence 状态机；
- parent aggregation；
- dependency unlock；
- child diff sandbox；
- pointer pilot executor；
- resolution receipt/generation lock；
- 幂等重放。

## Phase D — Targeted backflow

- 消费已经存在的真实批准；
- 没有批准时，升级 8 evidence、24 analysis、3 human、8 pointer 候选；
- 建立 20 dependency 最短解锁路径；
- 输出四案例面板和 blocker ledger。

## Phase E — Validation and publication

- 对抗测试、双跑、崩溃续跑；
- source-route + 全仓 pytest + scope audit；
- 至少 4 个 workstream commits（不含 seed）；
- 推送、CI、remote SHA；
- 生成 Night03 晨报和 Night04 队列。

## Progress

- [x] Phase A
- [ ] Phase B
- [ ] Phase C
- [ ] Phase D
- [ ] Phase E

## Discoveries

执行中追加，不删除历史记录。

- Bootstrap seed `77b46244c05724dc8158d25cec6f01f935ebcd8b` 的父提交、分支和 24 个包内路径通过硬门禁；
  原 bootstrap 脚本生成未跟踪 `.local/night_shift/night03_bootstrap.json` 后又要求 clean，已仅删除该明确本地文件。
- Night02 精确基线未跟踪完成收据中预告的 `publication/remote_delivery_receipt.json` 和 `publication/ci_status.md`；
  live GitHub 与已跟踪 `receipts/ns02_t46_commit_push_remote_ci.json` 共同证明远端 SHA/CI，未向 Night02 历史补造文件。
- Night02 物理产物为 78 个；69 项队列 SHA-256 为
  `dc2d6d6bb91b7ff326d3985d96f8eb8956a43710c61230eb06e6144e490e8ea1`，55 个 occurrence 来源哈希已验证，
  8 个 pointer occurrence 保持显式 `UNKNOWN`。

## Decisions

执行中追加。任何放宽门禁的决定必须引用明确的人类授权和 exact hash。

- 不修改 Night02 历史路径；发布/CI 路径偏差通过 Night03 审计器的已跟踪收据别名修正，并把实际证据路径写入审计产物。
- Phase A 继续维持 `0/63 resolved`、Goal open、sample quality/P2 false；路径兼容修复不构成研究 resolution。

## Remaining work

从 `task_queue.yaml` 自动同步；外部门禁必须保留为 `blocked_external`，
不能从列表中消失。

- Phase B：四类 exact-hash decision intake 与 false-resolution guard。
- Phase C：occurrence/parent/dependency state engine、sandbox、pointer pilot 与 receipt lock。
- Phase D：消费真实批准或完成 8/24/3/8 候选包、20 项依赖矩阵与 blocker ledger。
- Phase E：对抗、双跑、恢复、全回归、范围审计、分批提交、推送、CI、晨报和 Night04 队列。
