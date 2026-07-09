# Codex Task Card — R5 Patch 40：real sample pilot gate recheck

## 任务名称

real sample pilot gate recheck

## 背景

当前 close gate 显示 source-gapped real sample pilot 不允许。Patch 37-39 建立输入 registry / assumption registry / evidence ledger 后，需要重新运行 gate，但 gate 不应为了推进而强行放行；如果输入仍 pending，应继续保持 `source_gapped_real_sample_pilot_allowed: false`。

## 目标

1. 将 `scripts/r5_next_pilot_gate.py` 扩展为可读取：
   - R5_market_peer_input_registry.yaml
   - R5_forecast_assumption_registry.yaml
   - R5_evidence_request_review_ledger.yaml
2. 新增 config 规则：只有 reviewed/passed 的最小输入可解除 source-gapped pilot 禁止。
3. 输出新版 gate result：`r5_after_patch40_pilot_gate_result.json`。
4. 若仍未满足条件，必须诚实输出 false。

## 允许新增 / 修改文件

- `config/r5_next_pilot_gate_rules.yaml`
- `scripts/r5_next_pilot_gate.py`
- `tests/test_r5_next_pilot_gate_after_registries.py`
- `reports/p1_6/r5_after_patch40_pilot_gate_result.json`
- `reports/p1_6/R5_PATCH_40_REAL_SAMPLE_PILOT_GATE_RECHECK_READOUT.md`

## 禁止事项

- 不更改 gate 规则以绕过 TODO。
- 不把 pending registry 当作 reviewed。
- 不允许 sample-quality report 或 P2。
- 不生成真实个股报告。
- 不输出交易建议。

## Gate 逻辑要求

- `sample_quality_report_allowed` 必须继续依赖 forecast + valuation + evidence completeness。
- `p2_allowed` 必须继续为 false。
- `source_gapped_real_sample_pilot_allowed` 只有在以下最小条件满足时才可为 true：
  1. market_peer registry 至少 review_status reviewed 或 explicitly_degraded_but_reviewed；
  2. forecast assumption registry 至少 review_status reviewed 或 explicitly_degraded_but_reviewed；
  3. evidence request ledger 没有 accepted-null-evidence；
  4. source gaps 显式保留；
  5. no-advice gate pass。

## 验收标准

1. 测试覆盖 pending registry keeps pilot false。
2. 测试覆盖 reviewed degraded registry may allow source-gapped pilot but not sample-quality。
3. 测试覆盖 sample-quality 和 P2 仍被禁止。
4. readout 明确说明 gate 当前结论。

## 测试命令

```bash
python -m py_compile scripts/r5_next_pilot_gate.py
pytest -q tests/test_r5_next_pilot_gate.py tests/test_r5_next_pilot_gate_after_registries.py --tb=short
python scripts/r5_next_pilot_gate.py --readiness reports/p1_6/r5_readiness_gate_result.json --json reports/p1_6/r5_after_patch40_pilot_gate_result.json
```

## 输出要求

完成后输出：修改文件、测试结果、gate result summary、readout 路径。
