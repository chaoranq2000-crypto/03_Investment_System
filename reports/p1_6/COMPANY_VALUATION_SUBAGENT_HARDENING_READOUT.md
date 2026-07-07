# Company Valuation Subagent Hardening Readout

status: accepted

## Scope

本次只执行 `company-valuation` integration hardening pass：格式、解析、引用链、manifest 和 R4 估值章节收口。未进入 P2，未执行 live API，未新增估值结论，未补市场数据。

## Fixes

- 已按 LF 归一化本次范围内的 `.codex/config.toml`、company-valuation assets、stock-deep-dive valuation asset、workflow-run valuation artifacts、R4 报告和 manifest。
- `stock_analysis_pack.yaml#valuation_model` 已改为引用 `valuation/` 子目录下的 `company-valuation` 输出。
- `artifact_manifest.csv` 已登记 `valuation/valuation_model.yaml`、`valuation_snapshot.yaml`、`valuation_section_draft.md`、`valuation_gap_requests.yaml`、`valuation_quality_handoff.yaml`、`peer_comparison.csv`、`sensitivity_table.csv`。
- `R4_stock_deep_dive_v0_2.md` 估值章节已移除未被 `valuation_snapshot.yaml` 支撑的价格、市值、PE、PB、PS 数字，改为 `TODO_MARKET_DATA` / `TODO_PEER_DATA` / `TODO_FORECAST_MODEL_NET_PROFIT`。
- `valuation/sensitivity_table.csv` 已修复逗号字段 quoting，避免 CSV reader 串列。

## Boundary

- 保留 `TODO_MARKET_DATA`、`TODO_PEER_DATA`、`TODO_FINANCIAL_METRIC_PACK`、`TODO_FORECAST_MODEL_NET_PROFIT`、`MISSING_DISCLOSURE`。
- 估值、peer、technical context 不作为 segment exposure proof。
- 输出不包含 direct trading instructions, rating language, position sizing, stop instructions, or price instructions。

## Validation

- `tomllib` parses `.codex/config.toml`.
- `yaml.safe_load` parses 29 YAML files across the requested templates and the workflow run.
- `csv.DictReader` and `pandas.read_csv` parse 35 CSV files under `reports/workflow_runs/wf_20260703_stock_first_002837_invic/`.
- Smoke check confirms `stock_analysis_pack.yaml` valuation paths point to `valuation/` outputs and R4 valuation section has no unsupported legacy valuation numbers.
- `py_compile` passed for 85 Python files.
- Targeted `pytest` passed: 26 tests.
