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

- [ ] Phase A
- [ ] Phase B
- [ ] Phase C
- [ ] Phase D
- [ ] Phase E

## Discoveries

执行中追加，不删除历史记录。

## Decisions

执行中追加。任何放宽门禁的决定必须引用明确的人类授权和 exact hash。

## Remaining work

从 `task_queue.yaml` 自动同步；外部门禁必须保留为 `blocked_external`，
不能从列表中消失。
