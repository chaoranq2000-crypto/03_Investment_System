# R5 Patch 12 后续 Codex 任务包

这个任务包用于 Patch 1-12 推送后的修复与下一阶段推进。

核心判断：Patch 1-12 的文件和 readout footprint 已经出现，但 raw 文件检查显示多个关键脚本、模板和测试仍存在物理换行丢失、语法破坏、测试惰化或 readout 不可采信问题。因此下一阶段不能继续堆功能，必须先恢复可执行性。

## 使用方式

先把本目录加入仓库：

```text
git apply r5_after_patch12_codex_tasks.patch
```

然后按 `codex_tasks/r5_after_patch12/APPLY_ORDER.md` 的顺序，把每张任务卡交给 Codex 执行。

第一张任务卡必须是：

```text
codex_tasks/r5_after_patch12/R5_PATCH_13_FORMAT_SYNTAX_RECOVERY.md
```

## 验收边界

- 本补丁包只新增 Codex 任务卡和检查报告。
- 不直接修改现有 R5 实现。
- 不生成个股研究报告。
- 不接入真实 API。
- 不输出买入、卖出、持有、仓位建议。
