# R5 Patch 24 后补充与完善任务包

这个任务包用于最新工作区检查后的补充修复。

核心判断：Patch 13-24 的方向是正确的，因为 readiness gate 已经阻止进入 R5 / P2；但 raw 文件检查显示多个关键脚本、测试、YAML、Markdown 仍存在物理换行折叠，导致 readout 和 smoke 结果不可完全采信。

## 包含文件

```text
codex_tasks/r5_after_patch24/R5_AFTER_PATCH24_COMPLETION_REVIEW.md
codex_tasks/r5_after_patch24/APPLY_ORDER.md
codex_tasks/r5_after_patch24/R5_PATCH_25_RAW_FORMAT_RECOVERY_AND_REBASE.md
...
codex_tasks/r5_after_patch24/R5_PATCH_36_R5_CONTRACTS_CLOSE_READOUT_AND_NEXT_PILOT_GATE.md
```

## 使用方式

先应用本补丁包：

```bash
git apply r5_after_patch24_supplement_codex_tasks.patch
```

然后把 `APPLY_ORDER.md` 中的任务卡按顺序交给 Codex。

第一张任务卡必须是：

```text
codex_tasks/r5_after_patch24/R5_PATCH_25_RAW_FORMAT_RECOVERY_AND_REBASE.md
```

## 边界

本补丁包只新增 Codex 任务卡和检查报告，不直接修复代码、不生成个股报告、不接入真实 API、不输出交易建议。
