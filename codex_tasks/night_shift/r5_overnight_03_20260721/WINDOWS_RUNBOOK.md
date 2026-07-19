# Windows Runbook — Night03

## 1. 解压

将 `R5_Overnight_Mission_03_20260720.zip` 解压到任意临时目录。

## 2. 验证包

```powershell
python .\tools\verify_package.py .
```

## 3. 创建隔离 worktree

```powershell
.\bootstrap_worktree.ps1 `
  -RepoRoot "C:\Projects\03_Investment_System" `
  -WorktreeRoot "C:\Projects\03_Investment_System_night03"
```

Bootstrap 会核验：

- `origin/codex/r5-night02-contract-recovery` 精确等于 `069da527452def6c59c3772750e933d8611ccadf`；
- 源提交可获取；
- 目标 worktree 不污染 main；
- seed commit 只包含本任务包；
- package verifier 通过。

源分支不同但 SHA 相同，可显式传入：

```powershell
.\bootstrap_worktree.ps1 `
  -RepoRoot "C:\Projects\03_Investment_System" `
  -WorktreeRoot "C:\Projects\03_Investment_System_night03" `
  -SourceBranch "实际分支名"
```

## 4. Scheduled Task

- Working directory:
  `C:\Projects\03_Investment_System_night03`
- Prompt:
  `scheduled_task_prompt.txt`
- 建议启动：
  2026-07-20 23:00 Europe/London
- Stop claiming:
  2026-07-21 06:15
- Final readout:
  2026-07-21 06:30

## 5. 外部决定（可选）

Night03 能在没有外部决定时安全完成候选闭环。已有批准时，将 manifest 放入：

```text
reports/p1_6/r5_night_shift/r5_overnight_03_20260721\external_decisions\
```

必须使用 `templates\blank_decision_manifest.yaml` 的字段并绑定 exact hashes。
不要手工把状态文件中的 `proposed` 改成 `approved`。

## 6. 早晨检查

- `reports/p1_6/r5_night_shift/r5_overnight_03_20260721\morning_readout.md`
- `reports/p1_6/r5_night_shift/r5_overnight_03_20260721\progress\blocker_ledger.md`
- `reports/p1_6/r5_night_shift/r5_overnight_03_20260721\progress\four_case_dashboard.md`
- `reports/p1_6/r5_night_shift/r5_overnight_03_20260721\publication\remote_delivery_receipt.json`
- `reports/p1_6/r5_night_shift/r5_overnight_03_20260721\next_night_queue.yaml`

重点不是 Mission 是否写了 delivered，而是：

- resolved delta 是否有独立 receipts；
- 0/63 是否被如实保留；
- Goal 是否仍 open；
- Night02/Bundle17R 历史路径是否零变更。
