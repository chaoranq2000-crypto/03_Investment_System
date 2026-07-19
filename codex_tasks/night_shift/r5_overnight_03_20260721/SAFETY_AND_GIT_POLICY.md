# Safety and Git Policy

## Git

- 源提交硬锁：`069da527452def6c59c3772750e933d8611ccadf`
- 目标分支：`codex/r5-night03-targeted-backflow-intake`
- 独立 worktree：`C:\Projects\03_Investment_System_night03`
- seed commit 只能新增 `codex_tasks/night_shift/r5_overnight_03_20260721/**`
- 至少 4 个后续 workstream commits
- 禁止 `push --force`
- 禁止 PR
- 禁止 merge main
- 禁止修改或清理用户的 main worktree

## Historical immutability

以下全部只读：

- `reports/p1_6/r5_bundle17r/**`
- `reports/p1_6/r5_night_shift/r5_overnight_02_20260720/**`

Scope audit 必须证明相对 `069da527452def6c59c3772750e933d8611ccadf` 的上述路径变化数为 0。

## Human and research authority

自动流程不得：

- 生成 reviewer 身份；
- 填写人工 reviewed_at；
- 将 proposed 改为 approved；
- 将 candidate-ready 改为 resolved；
- 自动关闭研究 Goal；
- 自动开放 sample quality 或 P2。

## Evidence

- 不修改 `data/raw/**`；
- 不把用户样例当事实来源；
- 事实、估计、推断、管理层表述、分析师观点、未知必须区分；
- 缺失数据保持 `MISSING/UNKNOWN/LOW_CONFIDENCE`。
