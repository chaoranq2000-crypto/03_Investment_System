# R5_Overnight_Mission_03_20260720

这是 Night03 的可执行夜间任务包。它以 Night02 最终提交
`069da527452def6c59c3772750e933d8611ccadf` 为硬基线，读取 Night02 生成的 **69 项权威队列**，
将工作重点从“重建夜班运行时”切换到：

1. 外部决定的 exact-hash 安全摄取；
2. 8 个 pointer occurrence 的受控执行；
3. 8 个 evidence、24 个 analysis、3 个人审项的不可变候选包；
4. 20 个依赖项的真实解锁；
5. 只凭独立 resolution receipt 计算 blocker delta。

## 先验证包

```powershell
python .\tools\verify_package.py .
```

## 创建 Night03 worktree

```powershell
.\bootstrap_worktree.ps1 `
  -RepoRoot "C:\Projects\03_Investment_System" `
  -WorktreeRoot "C:\Projects\03_Investment_System_night03"
```

默认源分支：`codex/r5-night02-contract-recovery`
默认目标分支：`codex/r5-night03-targeted-backflow-intake`

Bootstrap 会：

- `git fetch origin`；
- 核验远端源分支精确等于 `069da527452def6c59c3772750e933d8611ccadf`；
- 创建隔离 worktree；
- 把本包复制到 `codex_tasks/night_shift/r5_overnight_03_20260721`；
- 创建一个只包含任务包的 seed commit；
- 运行 package verifier。

## Scheduled Task

工作目录设为：

```text
C:\Projects\03_Investment_System_night03
```

Prompt 使用 `scheduled_task_prompt.txt` 的全文。

## 重要真值

- Night02 Mission：`complete / delivered`
- 长期研究 Goal：`open_needs_targeted_backflow`
- 研究 blocker：`0/63 resolved`
- Night03 不得自动关闭 Goal、开放 sample quality 或进入 P2。
