# R5 Patch 30 — Readiness Gate Rebase on Real Smoke

status: `TASK_CARD`

## 背景

Patch 24 的 readiness gate 方向正确：它阻止了进入 R5 / P2。但该 gate 依赖的 smoke 和 inventory 需要在 Patch 25-29 修复后重新绑定。

## 目标

让 readiness gate 基于真实 smoke、真实 inventory、真实 truthfulness、真实 source gap 状态做决策。

## 允许修改

```text
config/r5_readiness_gate_rules.yaml
scripts/r5_readiness_gate.py
tests/test_r5_readiness_gate.py
reports/p1_6/r5_readiness_gate_result.json
reports/p1_6/R5_PATCH_30_READINESS_REBASE_READOUT.md
```

## 决策枚举

```text
R5_BLOCKED
R5_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY
R5_READY_FOR_SOURCE_GAPPED_REAL_SAMPLE_PILOT
```

任何情况下都必须保持：

```text
sample_quality_report_allowed = false
p2_allowed = false
```

直到后续显式任务解除。

## 全局禁止事项

- 不生成任何买入、卖出、持有、建仓、减仓、仓位建议。
- 不生成 sample-quality 个股报告。
- 不进入 P2。
- 不调用 live API。
- 不把 TODO / MISSING_DISCLOSURE / LOW_CONFIDENCE_CLUE_ONLY 写成事实。
- 不用 readout 自述替代实际命令、exit_code、stdout/stderr 和 artifact evidence。


## 必跑命令

```bash
python -m py_compile scripts/r5_readiness_gate.py
python -m pytest -q tests/test_r5_readiness_gate.py --tb=short
python scripts/run_r5_mvp_smoke.py --strict --json reports/p1_6/r5_mvp_smoke_result.json
python scripts/r5_readiness_gate.py --json reports/p1_6/r5_readiness_gate_result.json
```

## 验收标准

- 如果 smoke fail，decision 必须是 `R5_BLOCKED`。
- 如果 contracts pass 但 forecast/valuation/market/sentiment 仍 TODO，decision 只能是 `R5_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY`。
- 只有 source-gapped pack、evidence plan、valuation handoff、no-advice 全部满足且无工程 blocker 时，才允许 `R5_READY_FOR_SOURCE_GAPPED_REAL_SAMPLE_PILOT`。
- sample-quality 和 P2 仍为 false。
