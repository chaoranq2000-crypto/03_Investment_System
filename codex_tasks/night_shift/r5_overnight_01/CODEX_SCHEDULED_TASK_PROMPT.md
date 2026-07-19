# Codex Scheduled Task Prompt — R5 Overnight Mission 01

你正在执行一个完整夜班 Mission，而不是单个补丁任务。除非遇到本文定义的硬门禁，否则不要在完成第一项工作后停止；必须持续领取下一项 ready task，直到达到退出条件或到达停止领取时间。

## 工作上下文

- 源工作区：`C:\Projects\03_Investment_System_bf2`
- 源分支：`codex/r5-bundle17r-bf2-execution-receipts`
- 必须核验的源 SHA：`36a801efc2bf0af10ad9702b8c6266ebf1935d6f`
- 隔离 worktree：`C:\Projects\03_Investment_System_night01`
- 目标分支：`codex/r5-night01-autonomous-harness`
- 任务包仓库路径：`codex_tasks/night_shift/r5_overnight_01/`
- 外部任务包回退路径：`<PACKAGE_ROOT>`
- 时区：`Europe/London`
- 06:15 后停止领取新任务；06:30 前生成最终晨报

## 启动动作

1. 阅读仓库根 `AGENTS.md`，以及本包的 `START_HERE.md`、`OVERNIGHT_MISSION.md`、`SAFETY_AND_GIT_POLICY.md`、`BF2_INPUT_HANDOFF.md`、`EXECPLAN.md`、`task_queue.yaml` 和 `acceptance_matrix.yaml`。
2. 在源工作区执行 `git fetch --all --prune`。
3. 核验远端源分支 HEAD、本地源分支 HEAD 和指定 SHA 三者一致。
4. 不得修改脏的 `main`。创建或复用独立 worktree 和目标分支。
5. 对源工作区中的 `.local/` 与 `reports/p1_6/r5_bundle17r_bf2*` 做只读输入盘点；将需要的文件复制到隔离 worktree 的 `.local/night_shift/inputs/`，记录 SHA-256，但不得 `git add`。
6. 更新 `EXECPLAN.md` 的 Progress 和 Decisions；开始领取 `task_queue.yaml` 中最高优先级的 ready task。

## 持续循环

对每个 task：

1. 重新确认依赖完成、路径白名单和硬门禁；
2. 将 task 标记为 claimed/running，并写入原子状态与运行锁；
3. 实施代码、测试、配置或受控文档变更；
4. 执行 task 的 acceptance commands；
5. 生成 execution receipt，包含命令、退出码、输出摘要、产物哈希和当前提交；
6. 验收通过后创建逻辑清晰的 commit 并推送；
7. 更新 queue、ExecPlan、发现和决策；
8. 重新计算 ready tasks，继续下一项。

不要因为“本任务声明的文件已写完”就结束夜班。

## 自动执行边界

可自动执行：

- 队列、状态机、Schema、运行锁、恢复、验收和回执等工程实现；
- 从已有 BF2 工作单无损生成工程任务；
- 纯本地、可验证、不依赖新外部事实的工程修复；
- 测试、确定性检查、文档和晨报。

不可自动宣称解决：

- 需要新外部证据才能成立的研究 blocker；
- 需要研究员判断的 source mapping、经济解释或人工审核；
- sample quality、canonical state、P2 或 exact-hash 人审通过。

这些事项必须生成 failure/backflow packet，保留 blocker，不得伪造 pass。

## 强制真值

本夜开始时：6 个工作单均 pending，`0/63` blocker occurrence resolved。导入、分类、拆分、去重或创建子任务，都不得改变这两个事实，除非某一 blocker 经过完整证据、验收和回执链真实解决。

`case_id=__suite__` 必须合法；BF1 generation-lock 的真实结构兼容不得回退。

## 硬停止条件

遇到以下情况，停止修改并生成 `failure_packet.md`，但仍完成晨报：

- 源 SHA 不一致；
- 无法保证隔离 worktree；
- 发现需要 force push、修改脏 main、自动合并或越过人审；
- 需要凭空补研究事实或证据；
- 发现密钥、权限或凭据问题；
- 全量测试在一次定向修复后仍失败；
- 任务要求修改 canonical/sample-quality/P2 状态；
- 当前时间已过停止领取时间。

## 最终动作

1. 运行专项测试、source-route gate、本包新增测试和 `python -m pytest -q`；
2. 对夜班核心生成物进行两次独立运行并逐字节比较；
3. 检查 `git status --short`，保证 `.local/`、BF2 运行产物和未声明路径未进入提交；
4. 推送目标分支；不创建 PR、不合并 main；
5. 生成 `reports/p1_6/r5_night_shift/<run_id>/morning_readout.md`；
6. 明确写出：完成任务、提交 SHA、测试结果、真实 blocker 变化、剩余阻断、门禁状态、下一夜 ready queue 和需要人工决定的事项。
