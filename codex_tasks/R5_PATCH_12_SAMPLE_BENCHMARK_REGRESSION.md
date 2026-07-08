# Codex Task Card — R5 Patch 12：sample benchmark regression tests

## 任务名称

sample benchmark regression tests

## 目标

1. 把样例质量 rubric 固化为 regression tests。
2. 补 section density targets。
3. 样例报告只作为风格/密度 benchmark，不作为事实源。

## 允许新增 / 修改文件

- `benchmarks/r5_report_quality_rubric.yaml`
- `benchmarks/r5_section_density_targets.yaml`
- `benchmarks/sample_reports/README.md`
- `tests/test_r5_report_quality_rubric.py`
- `reports/p1_6/R5_PATCH_12_SAMPLE_BENCHMARK_REGRESSION_READOUT.md`

## 禁止事项

- 不修改 `reports/workflow_runs/` 历史 run。
- 不修改已有 R4 报告正文产物，除非本任务明确要求兼容指针。
- 不新增真实 API 调用，不执行联网下载。
- 不生成任何真实股票研究报告。
- 不计算真实 forecast 或真实 valuation，除非本任务明确只做 schema fixture。
- 不把 `TODO_SOURCE_REQUIRED`、`MISSING_DISCLOSURE`、`TODO_MODEL_INPUT` 写成事实。
- 不输出买入、卖出、持有、建仓、减仓、仓位建议、保证收益或自动交易指令。
- 不让 writer / composer 创造研究结论。

## 交付物 / 规则要求

- rubric 必须覆盖九章。
- forecast / valuation / source gap / no-advice gate 必须存在。
- YAML 可解析。

## 测试命令

~~~bash
python - <<'PY'
import yaml
for p in ['benchmarks/r5_report_quality_rubric.yaml','benchmarks/r5_section_density_targets.yaml']:
    with open(p, encoding='utf-8') as f:
        yaml.safe_load(f)
print('benchmark yaml ok')
PY
pytest tests/test_r5_report_quality_rubric.py
~~~

## 输出要求

完成后请输出：

1. 新增 / 修改文件列表；
2. 测试命令和结果；
3. 简短 diff summary；
4. 未完成项和 source gap；
5. 一个 readout 文件，放入 `reports/p1_6/`。
