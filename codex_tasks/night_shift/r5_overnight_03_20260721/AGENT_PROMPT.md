# Codex Agent Prompt — Night03

你正在 `C:\Projects\03_Investment_System_night03` 的隔离 worktree 中执行
`R5 Overnight Mission 03`。

1. 先读仓库 `AGENTS.md`、本目录 `START_HERE.md`、`OVERNIGHT_MISSION.md`、
   `EXECPLAN.md`、`task_queue.yaml`、`source_contract.yaml`。
2. 先运行：
   `python codex_tasks/night_shift/r5_overnight_03_20260721/tools/verify_package.py codex_tasks/night_shift/r5_overnight_03_20260721`
3. 执行 `ns03_t00`。任何 SHA、receipt、CI、queue count 或历史路径不一致均硬停止。
4. 逐项领取 dependency-ready 的最高优先级任务；每项先实现、再执行 acceptance，
   再写 receipt、更新 queue/ExecPlan、形成有意义 commit。
5. Night02 69 项为权威 research queue。不得压缩、重命名或重新发明 occurrence。
6. 外部决定缺失时：
   - imported resolution item 保持 `blocked_external` 或 `candidate_ready`；
   - 不增加 resolved；
   - 继续完成候选包、测试、矩阵、账本和发布任务。
7. 发现有效 exact-hash approved 决定时：
   - 逐项消费；
   - pointer 每波最多 2 项；
   - child diff 必须是批准路径子集；
   - 每项独立 acceptance 与 resolution receipt；
   - 重新计算 dependency 和 parent 状态。
8. 不修改 Night02、Bundle17R、canonical workflow state、raw evidence。
9. 不创建 PR、不合并 main、不 force push、不伪造人审、不开放 sample quality/P2。
10. 一直执行到 06:15 cutoff 或所有 wrapper delivery tasks 完成且 Night04 queue 就绪。
11. 最终晨报必须明确：
    - Mission outcome；
    - resolved delta；
    - candidate-ready 数；
    - blocked_external 数；
    - 每个 golden case 状态；
    - commits、tests、CI、remote SHA；
    - historical path diff；
    - Goal 仍是否 open；
    - Night04 carry-forward。
