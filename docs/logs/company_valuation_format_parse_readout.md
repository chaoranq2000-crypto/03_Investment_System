# Company Valuation Format Parse Readout

status: accepted

## Scope

本次只做 `company-valuation` subagent 集成相关 TOML / YAML 的格式与解析修复；未进入 P2，未新增估值结论，未补市场数据。

## Changes

- `.codex/config.toml` 的 `project_root_markers` 改为标准多行 TOML 数组，保留每个 `[[skills.config]]` 独立块。
- 目标 YAML 模板与 dry-run 产物统一增加显式 `---` 文档起始标记。
- 保留所有 `TODO_MARKET_DATA`、`TODO_PEER_DATA`、`TODO_FINANCIAL_METRIC_PACK`、`TODO_FORECAST_MODEL_NET_PROFIT` 和 no-advice 边界。

## Validation

- `tomllib` can parse `.codex/config.toml`.
- `yaml.safe_load` can parse all requested YAML templates and dry-run artifacts.
- Targeted pytest suites pass.
