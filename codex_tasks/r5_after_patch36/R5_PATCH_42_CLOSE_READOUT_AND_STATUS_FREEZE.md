# Codex Task Card — R5 Patch 42：close readout and status freeze

## 任务名称

close readout and status freeze

## 背景

Patch 37-41 完成后，需要一个诚实的 close readout。这个 readout 的目标不是宣布 R5 样例级完成，而是冻结当前状态：哪些输入 registry 建立了，哪些仍是 pending，source-gapped pilot 是否允许，sample-quality/P2 是否仍禁止。

## 目标

1. 运行严格 smoke / gate / composer degradation tests。
2. 输出 `R5_AFTER_PATCH42_CLOSE_READOUT.md`。
3. 输出 `r5_after_patch42_close_gate_result.json`。
4. 更新 canonical readout index（如项目已有该索引），但不改 global workflow kernel。

## 允许新增 / 修改文件

- `reports/p1_6/R5_AFTER_PATCH42_CLOSE_READOUT.md`
- `reports/p1_6/r5_after_patch42_close_gate_result.json`
- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md`（如已存在，仅追加指针）
- `tests/test_r5_readout_truthfulness.py`（仅在需要覆盖新增 readout 时修改）

## 禁止事项

- 不声称 sample-quality report 已完成，除非 gate 明确允许。
- 不声称 P2 已允许。
- 不忽略 pending / TODO。
- 不输出任何交易建议。
- 不修改历史 R4/R5 事实性产物。

## Close Readout 必须回答

1. Patch 37-41 是否完成。
2. 当前 R5 状态是什么。
3. source-gapped real sample pilot 是否允许。
4. sample-quality report 是否允许。
5. P2 是否允许。
6. strict smoke / gate / composer tests 结果。
7. 当前仍存在的 TODO。
8. 下一轮最多 3 个候选任务。

## 测试命令

```bash
python scripts/check_r5_artifact_format.py --strict --json reports/p1_6/r5_format_guard.json
python scripts/run_r5_mvp_smoke.py --strict --json reports/p1_6/r5_mvp_smoke_result.json
python scripts/r5_next_pilot_gate.py --readiness reports/p1_6/r5_readiness_gate_result.json --json reports/p1_6/r5_after_patch42_close_gate_result.json
pytest -q tests/test_r5_readout_truthfulness.py tests/test_r5_next_pilot_gate.py tests/test_r5_report_composer_degradation.py --tb=short
```

## 输出要求

完成后输出：测试命令和结果、close gate result、readout 路径、下一步建议，但不要继续执行下一步。
