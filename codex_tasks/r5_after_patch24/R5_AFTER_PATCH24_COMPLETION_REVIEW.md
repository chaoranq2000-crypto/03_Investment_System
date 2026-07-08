# R5 Patch 24 后最新工作区完成情况检查

status: `R5_BLOCKED_WITH_NON_EXECUTABLE_RAW_ARTIFACTS`

## 检查口径

本检查基于最新 GitHub `main` raw/tree 视图，不以 readout 的自述结论作为唯一依据。

重点检查对象：

- Patch 13-24 readout footprint
- R5 readiness gate / smoke wrapper / inventory / truthfulness gate
- R5 templates / example packs / tests 的物理换行与可执行性
- 002837 source-gapped R5 pack 与 gap plan

## 已完成的部分

1. Patch 13-24 的任务卡和 readout footprint 已经出现。
2. `reports/p1_6/R5_PATCH_24_READINESS_GATE_READOUT.md` 明确给出 `R5_BLOCKED`，没有误放行 sample-quality、真实 R5 个股 pilot 或 P2。
3. `reports/p1_6/r5_readiness_gate_result.json` 的决策字段同样显示：
   - `decision = R5_BLOCKED`
   - `can_enter_source_gapped_real_sample_pilot = false`
   - `sample_quality_report_allowed = false`
   - `p2_allowed = false`
4. `reports/p1_6/r5_mvp_smoke_result.json` 记录了 strict smoke 失败，失败项包括：
   - `r5_patch_inventory_check`
   - `r5_readout_truthfulness_gate`
5. `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_pack_source_gapped.yaml` 已存在，且语义上保留了 source gaps，没有把 forecast / valuation / market / sentiment 缺口写成事实。

## 阻断问题

### B1. raw 视图显示多个关键 Python 文件仍是 1 行 / 2 行文件

典型文件：

```text
scripts/check_r5_artifact_format.py
scripts/r5_patch_inventory_check.py
scripts/check_r5_readout_truthfulness.py
scripts/run_r5_mvp_smoke.py
src/research/forecast_model_builder.py
src/report/stock_report_writer.py
.agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py
tests/test_validate_r5_stock_research_pack.py
tests/test_r5_readiness_gate.py
```

风险：

- `#!/usr/bin/env python3 ... from __future__ import ...` 被折叠在一行时，整行可能被 shebang 注释吞掉，`py_compile` 会假阳性通过。
- `from __future__ import annotations from typing ...` 被折叠在一行时，语法上不可执行。
- 测试文件被折叠在一行时，pytest collect / import 结果不可采信。

### B2. 当前 format guard 不能保护自身

`check_r5_artifact_format.py` 本身在 raw 视图中为 2 行，但它没有有效保护自己、smoke wrapper、inventory checker、truthfulness checker 等 gate-of-gates 文件。

### B3. Patch 1-12 inventory 仍不通过

`r5_patch_1_12_inventory_status.yaml` 显示：

```text
inventory_status: claimed_complete_but_validation_failed
accepted: false
patches_checked: 12
blocking_patch_failures: 9
artifact_failures: 34
```

原因主要包括：

- expected artifact config 与实际落地文件命名不一致。
- Patch 4-12 多个 readout / contract / validator / test 仍缺失。
- inventory 自身也是一行 YAML，后续审计可读性差。

### B4. Patch 19 truthfulness gate 仍不通过

`r5_mvp_smoke_result.json` 中的 `r5_readout_truthfulness_gate` 失败，原因是历史 R5 readout 缺少：

- files_added
- files_modified
- commands_run
- exit_codes
- stdout_or_stderr_summary
- known_todos
- next_recommended_patch
- artifact hash / line count / checked count / inventory evidence

这些不能靠事后补写虚假命令解决，应建立 canonical readout index，把历史 readout 标记为 legacy/non-canonical，或者用 rerun supplement readout 重新生成真实证据。

### B5. 002837 source-gapped pack 存在，但仍不是 sample-quality

当前 pack 明确保留：

- `forecast_model_pack.status = TODO`
- `valuation_pack.status = TODO`
- `technical_market_pack.status = TODO`
- `sentiment_event_pack.status = TODO`
- 业务拆分中的收入、毛利率、利润贡献为 `MISSING_DISCLOSURE`

这是正确边界，但文件物理格式仍需恢复，且 evidence request queue 还没变成可执行状态。

## 当前验收结论

```text
R5 contracts direction: partially present
R5 readiness gate: correctly blocked
R5 executable toolchain: not trusted
R5 sample-quality report: not allowed
R5 real source-gapped pilot: not allowed until raw format + inventory + truthfulness are repaired
P2: not allowed
```

## 下一步原则

1. 不进入 P2。
2. 不生成 R5 sample-quality 个股报告。
3. 不继续堆 forecast / valuation 业务功能。
4. 先修 raw 物理换行、可执行 guard、inventory、truthfulness。
5. 修完后才重新审查 002837 source-gapped pack。
