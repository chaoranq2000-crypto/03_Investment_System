# R5 Patch 29 — Smoke Result Trust Boundary

status: `TASK_CARD`

## 背景

当前 `run_r5_mvp_smoke.py` 和 smoke result 自身也曾出现一行化风险。需要让 smoke wrapper 记录 provenance，并确保它不是空模块假执行。

## 目标

重建可信 single smoke command：

```text
python scripts/run_r5_mvp_smoke.py --strict --json reports/p1_6/r5_mvp_smoke_result.json
```

## 允许修改

```text
scripts/run_r5_mvp_smoke.py
tests/test_run_r5_mvp_smoke.py
reports/p1_6/r5_mvp_smoke_result.json
reports/p1_6/R5_PATCH_29_SMOKE_TRUST_BOUNDARY_READOUT.md
```

## 新增 smoke provenance 字段

```yaml
generated_at:
repo_root:
python_executable:
python_version:
platform:
steps:
  - name
  - command
  - exit_code
  - duration_seconds
  - stdout_tail
  - stderr_tail
  - artifact_outputs
  - trust_boundary_note
```

## 要求

1. smoke wrapper 必须先运行 `r5_artifact_format_guard`，且 guard 必须检查 smoke wrapper 自身。
2. 任一子命令非 0 时，strict smoke 必须返回非 0。
3. stdout/stderr 必须完整保留或保留 tail + raw log path。
4. JSON 必须多行缩进。
5. 不能把 advisory failure 说成 pass。

## 全局禁止事项

- 不生成任何买入、卖出、持有、建仓、减仓、仓位建议。
- 不生成 sample-quality 个股报告。
- 不进入 P2。
- 不调用 live API。
- 不把 TODO / MISSING_DISCLOSURE / LOW_CONFIDENCE_CLUE_ONLY 写成事实。
- 不用 readout 自述替代实际命令、exit_code、stdout/stderr 和 artifact evidence。


## 必跑命令

```bash
python -m py_compile scripts/run_r5_mvp_smoke.py
python -m pytest -q tests/test_run_r5_mvp_smoke.py --tb=short
python scripts/run_r5_mvp_smoke.py --strict --json reports/p1_6/r5_mvp_smoke_result.json
```

## 验收标准

- 如果 Patch 27/28 未通过，smoke 必须 fail，且原因清楚。
- 如果 Patch 27/28 已通过，smoke 应 pass。
- 无论 pass/fail，readout 都必须记录真实 exit_code。
