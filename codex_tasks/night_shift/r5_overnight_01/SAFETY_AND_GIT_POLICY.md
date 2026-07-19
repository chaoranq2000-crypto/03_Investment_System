# Safety and Git Policy

## Git isolation

- 只在隔离 worktree 中执行实现。
- 源工作区 `C:\Projects\03_Investment_System_bf2` 仅用于 fetch、SHA 核验和读取未跟踪 BF2 输入。
- 不修改脏的 `main`，不 checkout main 来“清理工作区”。
- 不使用 `git reset --hard`、`git clean -fdx`、force push、rebase main 或自动 merge。
- 目标分支固定为 `codex/r5-night01-autonomous-harness`，除非该分支已存在且指向不兼容历史；这种情况生成 failure packet。

## Commit policy

建议最多三组逻辑提交：

1. `feat(night-shift): add queue runtime and recovery`
2. `feat(night-shift): seed BF2 work orders and receipts`
3. `test(night-shift): add regression, readout, and mission docs`

每个提交前必须运行对应 targeted tests。最终推送前必须运行全量测试。

## 研究真实性

- 工程任务生成不等于研究 blocker 解决。
- 不得将缺少外部证据的问题标为 pass。
- 不得把模型假设、管理层表述或分析师观点改写为事实。
- 不得自动填写人工审核结果。
- 不得改变 `sample_quality_allowed=false`、`p2_allowed=false` 或 canonical state，除非另有独立人审任务和精确哈希决定；本 Mission 没有此授权。
- 报告和晨报不得输出直接买卖、仓位或保证收益指令。

## 路径边界

优先允许：

```text
src/maintenance/night_shift/**
scripts/run_r5_night_shift.py
scripts/run_r5_night_shift.ps1
config/r5_night_shift*.yaml
config/r5_night_shift*.json
tests/test_r5_night_shift*.py
tests/fixtures/r5_night_shift/**
codex_tasks/night_shift/r5_overnight_01/**
reports/p1_6/r5_night_shift/**
.local/night_shift/**   # 仅运行时，不得提交
```

禁止：

```text
data/raw/**
reports/p1_6/R5_READOUT_CANONICAL_INDEX.md
config/r5_readout_canonical_index.yaml
未声明的历史 Bundle 产物
.local/** 进入 git index
reports/p1_6/r5_bundle17r_bf2* 进入 git index
```

如 safe pilot 确实需要其他实现路径，必须：

1. 从原 BF2 work order 读取其 allowed paths；
2. 在 receipt 中记录扩展理由；
3. 运行该路径对应专项测试；
4. 不得修改共享 canonical 状态面。

## 自动停止门禁

以下事件发生时停止继续实现：

- baseline SHA mismatch；
- worktree isolation 失败；
- 需要秘密凭证或权限；
- 任务需要新事实但没有来源；
- 任务要求人工评价或 exact-hash 审核；
- 全量回归经一次定向修复仍失败；
- 当前时间超过 stop-claiming cutoff；
- 发现任何会错误开放研究门禁的要求。
