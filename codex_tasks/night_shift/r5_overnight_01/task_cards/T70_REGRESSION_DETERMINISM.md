# ns01_t70_regression_determinism — Regression and Determinism

## Goal

证明新增夜班运行时没有破坏现有 R5 门禁，并且核心输出可复现。

## Required gates

- 新增 night-shift tests；
- 已有 BF2 专项；
- EX1 专项；
- source-route gate；
- `python -m pytest -q`；
- `git diff --check`；
- BF2 seed 双跑；
- morning readout 双跑；
- no tracked `.local` / BF2 run outputs；
- no canonical/sample-quality/P2 auto-advance。

## Failure handling

允许一次定向修复。修复后仍失败则停止实现，生成 failure packet，并继续生成晨报。
