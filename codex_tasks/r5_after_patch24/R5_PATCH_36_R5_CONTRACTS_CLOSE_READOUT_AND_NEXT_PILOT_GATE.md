# R5 Patch 36 — R5 Contracts Close Readout and Next Pilot Gate

status: `TASK_CARD`

## 背景

Patch 25-35 修完后，需要一个诚实的 close readout：总结 R5 contracts 是否可执行、是否允许进入 source-gapped real sample pilot、是否仍禁止 sample-quality 和 P2。

## 目标

生成 R5 contracts close readout 和下一阶段 pilot gate。

## 允许修改

```text
reports/p1_6/R5_AFTER_PATCH24_SUPPLEMENT_CLOSE_READOUT.md
reports/p1_6/r5_after_patch24_close_gate_result.json
config/r5_next_pilot_gate_rules.yaml  # 如需要
scripts/r5_next_pilot_gate.py  # 如需要
tests/test_r5_next_pilot_gate.py  # 如需要
```

## close readout 必须回答

1. Patch 25-35 是否全部完成？
2. 哪些命令跑过？exit_code 是什么？
3. 当前 R5 状态是：
   - `R5_BLOCKED`
   - `R5_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY`
   - `R5_READY_FOR_SOURCE_GAPPED_REAL_SAMPLE_PILOT`
4. 是否允许 sample-quality report？必须为 false。
5. 是否允许 P2？必须为 false。
6. 如果允许 source-gapped pilot，pilot 的输入和边界是什么？
7. 如果不允许，阻断项是什么？

## 全局禁止事项

- 不生成任何买入、卖出、持有、建仓、减仓、仓位建议。
- 不生成 sample-quality 个股报告。
- 不进入 P2。
- 不调用 live API。
- 不把 TODO / MISSING_DISCLOSURE / LOW_CONFIDENCE_CLUE_ONLY 写成事实。
- 不用 readout 自述替代实际命令、exit_code、stdout/stderr 和 artifact evidence。


## 必跑命令

```bash
python scripts/check_r5_artifact_format.py --strict --json reports/p1_6/r5_format_guard.json
python scripts/run_r5_mvp_smoke.py --strict --json reports/p1_6/r5_mvp_smoke_result.json
python scripts/r5_readiness_gate.py --json reports/p1_6/r5_readiness_gate_result.json
python -m pytest -q tests/test_r5_readiness_gate.py tests/test_run_r5_mvp_smoke.py --tb=short
```

## 验收标准

- close readout 是多行 Markdown。
- JSON gate result 是多行 JSON。
- 不允许 sample-quality / P2。
- 不用“全部完成”掩盖 TODO。
- 给出下一阶段最多 3 个候选任务，不继续执行。
