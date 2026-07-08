# R5 Patch 34 — Forecast Valuation Input Interlock

status: `TASK_CARD`

## 背景

当前 `forecast_model.yaml` 出现默认 8% / 10% 增长率估计，这在缺 reviewed assumptions 时容易被误读为真实预测。R5 必须禁止无输入的 pseudo forecast 升级。

## 目标

建立 forecast / valuation 输入互锁：没有 reviewed inputs 时，只能输出 TODO_MODEL_INPUT / TODO_MARKET_DATA / TODO_PEER_DATA，不能输出数字化预测或估值判断。

## 允许修改

```text
src/research/forecast_model_builder.py
src/research/valuation_snapshot_builder.py  # 如存在
.agents/skills/stock-deep-dive/references/r5_forecast_valuation_interlock.md
tests/test_r5_forecast_valuation_interlock.py
reports/workflow_runs/wf_20260703_stock_first_002837_invic/forecast_model.yaml
reports/p1_6/R5_PATCH_34_FORECAST_VALUATION_INTERLOCK_READOUT.md
```

## 要求

1. builder 不得在没有 reviewed assumptions 时自动生成 8% / 10% 等默认增长率。
2. 如果只有公司层面历史收入，forecast 输出可以保留 anchor，但 forecast values 必须是 TODO。
3. valuation 缺 market/peer 时必须保持 TODO，不得输出合理市值或目标价。
4. interlock 必须把“历史指标锚点”和“预测值”分开。

## 全局禁止事项

- 不生成任何买入、卖出、持有、建仓、减仓、仓位建议。
- 不生成 sample-quality 个股报告。
- 不进入 P2。
- 不调用 live API。
- 不把 TODO / MISSING_DISCLOSURE / LOW_CONFIDENCE_CLUE_ONLY 写成事实。
- 不用 readout 自述替代实际命令、exit_code、stdout/stderr 和 artifact evidence。


## 必跑命令

```bash
python -m py_compile src/research/forecast_model_builder.py
python -m pytest -q tests/test_r5_forecast_valuation_interlock.py --tb=short
python - <<'PY'
import yaml
from pathlib import Path
p = Path('reports/workflow_runs/wf_20260703_stock_first_002837_invic/forecast_model.yaml')
data = yaml.safe_load(p.read_text(encoding='utf-8'))
assert data['model_input_status']['revenue_forecast'] in ('TODO_MODEL_INPUT', 'blocked_without_reviewed_assumptions')
print('forecast interlock ok')
PY
```

## 验收标准

- 缺 reviewed assumptions 时没有 2026E-2028E revenue 数字预测。
- readout 说明为何不允许默认增长率。
- no-advice 仍通过。
