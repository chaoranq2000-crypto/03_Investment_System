# R5 Overnight Mission 01 — Autonomous Harness + BF2 Activation

## 这是什么

这是一个可直接交给 Codex 夜班执行的 **Mission 任务包**。它不是“完成声明”，也不是只写计划不改代码的普通任务卡。

本包要求 Codex 在真实仓库中：

1. 从已推送的 BF2 execution-receipts 提交建立隔离 worktree；
2. 实现最小、可恢复、可审计的夜班任务运行时；
3. 将本地真实 BF2 的 6 个工作单和 63 个 blocker occurrence 无损导入夜班队列；
4. 自动执行仅需本地工程修改的安全工作；
5. 对需要新证据、研究判断或人工审核的事项生成阻断包，不得伪造解决；
6. 完成专项测试、全量测试、确定性检查、提交和推送；
7. 在早晨输出一份可核验的 `morning_readout.md`。

## 当前基线

- 仓库：`chaoranq2000-crypto/03_Investment_System`
- 源分支：`codex/r5-bundle17r-bf2-execution-receipts`
- 源提交：`36a801efc2bf0af10ad9702b8c6266ebf1935d6f`
- 本地源工作区：`C:\Projects\03_Investment_System_bf2`
- 建议隔离 worktree：`C:\Projects\03_Investment_System_night01`
- 建议目标分支：`codex/r5-night01-autonomous-harness`
- 研究门禁：必须保持 `needs_targeted_backflow`
- 真实 BF2 状态：6 个工作单均为 `pending`；`0/63` blocker occurrence 已解决

基线 SHA 必须在执行时由 Codex 重新核验。SHA 不一致时不得“自动适配后继续”，而要生成 baseline mismatch failure packet。

## 最快使用方式

### 方式 A：先把任务包安装进仓库

在 PowerShell 中运行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\tools\install_into_repo.ps1 `
  -RepoRoot 'C:\Projects\03_Investment_System_bf2' `
  -PackageRoot '<解压后的本包路径>'
```

随后在 Codex Scheduled Task 中粘贴：

```text
读取并执行：
C:\Projects\03_Investment_System_bf2\codex_tasks\night_shift\r5_overnight_01\CODEX_SCHEDULED_TASK_PROMPT.md
```

### 方式 B：不安装，直接把外部路径交给 Codex

粘贴 `CODEX_SCHEDULED_TASK_PROMPT.md` 的完整内容，并把其中的 `<PACKAGE_ROOT>` 替换为本包解压路径。

## 首要阅读顺序

1. `CODEX_SCHEDULED_TASK_PROMPT.md`
2. `OVERNIGHT_MISSION.md`
3. `SAFETY_AND_GIT_POLICY.md`
4. `BF2_INPUT_HANDOFF.md`
5. `EXECPLAN.md`
6. `task_queue.yaml`
7. `acceptance_matrix.yaml`
8. `task_cards/`

## 任务包与实现的区别

本包自身是 Mission seed，因此 `package_mutates_runtime=false`；但夜班 Mission 的验收明确要求 `mission_must_mutate_runtime=true`。只有真正新增运行时代码、测试、配置和可执行入口，才算完成本夜核心工程目标。

## 本夜成功的最低标准

- 夜班队列合同、状态机、运行锁、恢复、验收回执和晨报生成器已实现；
- 6 个 BF2 工作单和 63 个 blocker occurrence 被无损、幂等导入；
- `case_id=__suite__` 和 BF1 generation-lock 兼容性保留；
- 至少完成一次安全 pilot，或生成可证明“没有安全自动任务”的 `no_safe_pilot` 记录；
- 全量测试通过；
- 确定性双跑通过；
- 没有将 `.local/`、真实 BF2 运行产物或未声明路径混入提交；
- 没有创建 PR、合并 `main`、自动开放 sample quality、canonical state 或 P2；
- 分支已推送，晨报列出提交、测试、剩余阻断和下一夜队列。
