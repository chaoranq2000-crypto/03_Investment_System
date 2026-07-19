# ns01_t00_preflight — Preflight

## Goal

建立可证明的精确基线、隔离 worktree 和只读本地 BF2 输入集。

## Steps

1. `git fetch --all --prune`。
2. 核验远端分支、本地分支和指定 SHA。
3. 确认源工作区的脏文件状态并记录，不做清理。
4. 创建隔离 worktree 与目标分支。
5. 枚举源 `.local/` 和 `reports/p1_6/r5_bundle17r_bf2*`。
6. 生成 SHA-256 manifest，复制必要输入到隔离 worktree `.local/night_shift/inputs/`。
7. 解析 `.github/workflows`，记录 EX1、BF2、source-route 和通用 CI 的本地等价命令。

## Acceptance

- HEAD 精确等于指定 SHA；
- 隔离 worktree 与源工作区路径不同；
- 输入 manifest 可复算；
- 没有任何源未跟踪文件进入 git index；
- 生成 preflight readout。
