# R5 Bundle 8.4 — M3/M4 Integration Gate

## 目标

仅判断证据覆盖与分析输入是否准备好进入 Bundle 9。

## 执行

```bash
python scripts/run_r5_bundle8_research_depth_gate.py --repo-root .
```

## 通过条件

- Evidence coverage gate：pass；
- Analysis pack gate：pass；
- 原始输入与生成物可重复重建；
- focused tests、全仓库 tests 和 CI 通过；
- truthfulness/no-advice 边界未退化。

## 明确不做

- 不修改 workflow state；
- 不 resolve TODO；
- 不更新 canonical index；
- 不重新生成 Reader；
- 不自动 close Bundle 8。

通过后另建 close-only patch，再进入 Bundle 9（M5+M6）。
