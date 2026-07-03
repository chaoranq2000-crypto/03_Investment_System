# Data Layer Development Task Breakdown

生成日期：2026-07-03
来源补丁包：`data_layer_workflow_patch.zip`
范围：后续编码、调试与验收拆解；本文件不替代 `docs/workflows/DATA_LAYER_WORKFLOW.md`。

## 0. 本轮补丁合并状态

已完成：

- 合并 `docs/workflows/DATA_LAYER_WORKFLOW.md`。
- 合并 `docs/adr/ADR_0002_data_layer_as_evidence_ingest_subsystem.md`。
- 合并 `docs/plans/DATA_LAYER_CODEX_EXECUTION_PLAN.md` 和 `docs/plans/DATA_LAYER_ACCEPTANCE_CHECKLIST.md`。
- 合并 evidence-ingest 的 source adapter、structured data、market context、data quality gate references 和模板资产。
- 将新 references 加入 `.agents/skills/evidence-ingest/SKILL.md`。
- 审阅并合并 `config/data_source_registry_overlay.yaml` 的可执行部分到 `config/source_registry.yaml`。

保留边界：

- 本轮不实现真实 API downloader。
- 本轮不写入 Tushare token。
- 本轮不修改正式 `data/manifests/evidence_manifest.csv`。
- 本轮不生成投资建议、交易信号或 watchlist 决策。

## 1. 当前代码基线观察

`src/ingest/structured_api_pull.py` 已具备：

- 本地 CSV/JSON fixture 输入。
- raw snapshot 不覆盖写入。
- `api_params_hash` 生成。
- normalized CSV 和 metric draft 生成。

需要修正：

- 增加 `--plan data_request_plan.yaml` 读取。
- 增加 `--dry-run`，只输出 endpoint、params、output paths，不访问网络。
- 将 manifest 枚举改回当前 B1 合同：`raw_archive_policy=snapshot_archived`、`parse_status=parsed|not_required|partial|failed`、`candidate_status=generated|blocked|not_generated`。
- 将 `source_group=structured_api` 改为 registry 中的 `structured_database`、`structured_database_fallback` 或 `market_data_adapter`。
- 将 `allowed_claim_types=metric_snapshot` 改为合同允许的 `metric_statement`，并在 notes 中说明 snapshot 口径。

现有 Tushare 脚本：

- `src/ingest/fetch_tushare_financial_snapshots.py`
- `src/ingest/fetch_tushare_stock_basic_snapshot.py`

需要改造为 adapter 模块或复用 adapter 接口，避免一组固定股票/固定日期的专用脚本成为生产入口。

现有 market context 相关代码：

- `src/ingest/market_snapshot_pull.py` 只登记离线 market fixture。
- `src/research/technical_snapshot_builder.py` 已能生成最小 technical snapshot，但还不满足 MA5/MA10/MA20/MA60、20d/60d 涨跌幅、成交量趋势完整契约。
- `src/research/market_sentiment_pack_builder.py` 已保持 clue-only 边界。
- 尚未看到 `valuation_snapshot` builder 和 `data_layer_quality_review.py`。

## 2. 推荐开发顺序

### DL-B1 Adapter Plan Reader

目标文件：

- `src/ingest/structured_api_pull.py`
- `tests/test_structured_api_pull_plan_reader.py`

验收：

- `--plan` 可读取 `.agents/skills/evidence-ingest/assets/data_request_plan_template.yaml` 派生出的请求计划。
- `--dry-run` 无 token、无网络也返回成功，并生成 run readout。
- 旧的 `--input-csv` / `--input-json` fixture 模式仍通过。
- 输出 manifest 枚举全部通过 `validate_manifest.py --no-path-check`。

### DL-B2 Tushare Adapter

目标文件：

- `src/ingest/adapters/tushare_adapter.py`
- `tests/test_tushare_adapter_contract.py`

第一版 API：

- `stock_basic`
- `daily_basic`
- `income`
- `balancesheet`
- `cashflow`
- `fina_indicator`
- `fina_mainbz`

验收：

- 无 `TUSHARE_TOKEN` 时 dry-run / BLOCKED readout 不失败。
- fixture income 生成 manifest row 和 metric candidates。
- `fina_mainbz` 只生成 business segment metric candidates，不生成 exposure claim。
- 参数变化导致 `api_params_hash` 变化。
- token 值不写入任何输出文件。

### DL-B3 Baostock Adapter

目标文件：

- `src/ingest/adapters/baostock_adapter.py`
- `tests/test_baostock_adapter_contract.py`

第一版 API：

- `query_stock_basic`
- `query_history_k_data_plus`
- `query_profit_data`
- `query_balance_data`
- `query_cash_flow_data`

验收：

- 本机未安装 baostock 时测试进入 fixture/BLOCKED 路径，不失败。
- 真实调用路径必须 `login -> query -> logout`。
- K 线 fixture 可生成 technical snapshot seed。
- 不生成 business exposure claim。

### DL-C1 Valuation Snapshot Builder

目标文件：

- `src/ingest/build_valuation_snapshot.py`
- `tests/test_valuation_snapshot_builder.py`

输出：

- `reports/workflow_runs/<workflow_id>/valuation_snapshot.yaml`

最低字段：

- `price`
- `market_cap`
- `pe_ttm`
- `pb`
- `ps`
- `turnover_rate`
- `trade_date`
- `source_evidence_id`

验收：

- 缺关键字段时写 `TODO_MARKET_DATA` 或 `MISSING`，不伪造估值结论。
- `source_evidence_id` 可追溯到 manifest 或 fixture evidence id。

### DL-C2 Technical Snapshot Builder Upgrade

目标文件：

- `src/research/technical_snapshot_builder.py` 或迁移到 `src/ingest/build_technical_snapshot.py`
- `tests/test_technical_snapshot_builder.py`

验收：

- 输出 MA5/MA10/MA20/MA60。
- 输出 20d/60d pct change。
- 输出 volume trend。
- `notes` 明确 technical snapshot 不是交易建议。

### DL-D1 Data Layer Quality Gate

目标文件：

- `src/qa/data_layer_quality_review.py`
- `tests/test_data_layer_quality_gate.py`

检查：

- G-DL1 source permission。
- G-DL2 raw archive。
- G-DL3 reproducibility / `api_params_hash`。
- G-DL4 field schema。
- G-DL5 metric-only boundary。
- G-DL6 freshness。
- G-DL7 license / token leak。
- G-DL8 downstream pack completeness。

验收：

- 输出 `data_layer_quality_report.md` 和 `data_layer_issue_list.csv`。
- high issue 能定位到具体 `target_artifact`。
- token 泄露、raw 覆盖、metric-only 越界必须 high。

### DL-E1 002837 Data-layer Run

目标目录：

- `reports/workflow_runs/wf_20260703_data_layer_002837_invic/`

最低产物：

- `data_request_plan.yaml`
- `adapter_run_queue.yaml`
- `valuation_snapshot.yaml`
- `technical_snapshot.yaml`
- `financial_metric_pack.csv`
- `source_gap_report.md`
- `data_layer_quality_report.md`
- `workflow_readout.md`

验收：

- `status: accepted_with_todos` 或 `accepted`。
- high issues 为 0。
- no-advice gate 通过。
- 没有用 Tushare/Baostock 证明业务暴露。

### DL-F Stock Report Readiness Bridge

目标文件：

- `.agents/skills/stock-deep-dive/SKILL.md`
- `.agents/skills/quality-review/SKILL.md`
- 必要时新增 stock-deep-dive reference。

验收：

- 缺 `valuation_snapshot.yaml` 时报告只能写 `TODO_MARKET_DATA`。
- 缺 `technical_snapshot.yaml` 时报告只能写 `TODO_MARKET_DATA`。
- 缺 `peer_market_snapshot.csv` 时同行比较只能写 `TODO_PEER_DATA`。
- 缺官方披露时不得写 business exposure fact。

## 3. 建议验收命令

```powershell
conda run -p .\.conda\investment-system python .\.agents\skills\evidence-ingest\scripts\validate_manifest.py --help
conda run -p .\.conda\investment-system python -m pytest -q tests/test_structured_api_pull.py tests/test_technical_snapshot_builder.py
conda run -p .\.conda\investment-system python -m pytest -q tests/test_tushare_adapter_contract.py tests/test_baostock_adapter_contract.py tests/test_data_layer_quality_gate.py
conda run -p .\.conda\investment-system python -m pytest -q
```

## 4. Stop Conditions

停止后续开发并回报用户，如果出现：

- API token 被写入 repo 文件。
- adapter 直接写股票报告或 watchlist。
- Tushare/Baostock 生成 business exposure claim。
- raw snapshot 被覆盖。
- 无 `api_params_hash` 的结构化 metric 被 promoted。
- data quality gate 无法定位具体 artifact。
- data layer 生成买卖建议或交易指令。
