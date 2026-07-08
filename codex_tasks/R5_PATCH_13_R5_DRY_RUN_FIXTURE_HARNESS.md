# Codex Task Card — R5 Patch 13：single-stock R5 dry-run fixture harness

## 任务名称

single-stock R5 dry-run fixture harness

## 目标

1. 用离线 fixture 验证 R5 pack → validators → quality gate → report plan。
2. 不联网、不使用真实股票数据、不生成真实研究结论。
3. 验证 source-gapped draft 和 blocked 两种路径。

## 允许新增 / 修改文件

- `tests/fixtures/r5_dry_run/minimal_valid_pack.yaml`
- `tests/fixtures/r5_dry_run/source_gapped_pack.yaml`
- `tests/test_r5_dry_run_harness.py`
- `scripts/r5_dry_run_harness.py`
- `reports/p1_6/R5_PATCH_13_R5_DRY_RUN_FIXTURE_HARNESS_READOUT.md`

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

- minimal fixture 可通过结构校验。
- source-gapped fixture 必须输出 downgrade。
- high issue fixture 不得 accepted。

## 测试命令

~~~bash
python -m py_compile scripts/r5_dry_run_harness.py
pytest tests/test_r5_dry_run_harness.py
~~~

## 输出要求

完成后请输出：

1. 新增 / 修改文件列表；
2. 测试命令和结果；
3. 简短 diff summary；
4. 未完成项和 source gap；
5. 一个 readout 文件，放入 `reports/p1_6/`。
