# R5 Bundle 5.1 — Real Input Inventory and Provenance Readout

status: blocked_source_gapped

## close_decision

- workflow_id: `wf_20260703_stock_first_002837_invic`
- stock_code: `002837`
- G1 Evidence Gate: `fail`
- reviewed_input_dropzone_files: `0`
- reviewed_input_records: `0`
- valid_accepted_core_input_types: `0/5`
- source_request_queue: `10 requests / 7 source gaps`
- review_ledger: `10 pending / 0 accepted`
- card_5_1_inventory_completed: `true`
- card_5_1_stop_condition_triggered: `true`
- card_5_2_allowed: `false`
- promotion_allowed: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`

本卡作为“真实输入清点卡”已完成，但真实输入门禁未通过。`validate_r5_reviewed_input_dropzone.py` 对不存在的 dropzone 返回 `pass checked_files=0`，这里只表示“没有格式错误可报”，不表示输入就绪；focused inventory 明确将其解释为 `empty_valid_but_source_gapped`。

## input_matrix

| input_type | physical reviewed record | valid accepted | current evidence/provenance | decision |
|---|---:|---:|---|---|
| `business_disclosure` | 0 | 0 | 两个 manifest 记录指向同一份 7 页 2025 年年报摘要，SHA256 相同；一个 global `reviewed`，一个 workflow-local `draft`；均不是 Bundle 5 reviewed-input record，且无 reviewer/reviewed_at | blocked |
| `market_snapshot` | 0 | 0 | 现有 `market_snapshot.csv` 为 `not_acquired / TODO_MARKET_DATA`；workflow-local Tushare 材料标为 fixture/draft | blocked |
| `peer_snapshot` | 0 | 0 | 现有 peer 表为 TODO/fixture-only，没有 reviewed peer set 或同口径倍数 | blocked |
| `forecast_assumptions` | 0 | 0 | 五个核心 driver 均为 pending / `TODO_MODEL_INPUT`，evidence_ids 为空，无 reviewer 元数据 | blocked |
| `valuation_inputs` | 0 | 0 | 真实 `R5_valuation_input_registry.yaml` 不存在；现有 readiness 仍依赖 market/peer/forecast TODO | blocked |
| `sentiment_event_sources` | 0 | 0 | 可选增强输入；现有请求均 pending，不阻塞本卡之外的核心计数 | optional missing |

完整 nullable provenance、request_id、registry target、missing field 和 evidence-candidate 记录见：

- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_real_input_inventory.yaml`

## provenance_review

- 官方候选原始文件：`data/raw/annual_reports/annual_report_002837_invic_2025_0f8fcf.pdf`，SHA256 `CE7F64A9337742B1CECEF56FB4A9EA7E558715F7BD1DCA8B5E64003F71DAAFA1`。
- workflow-local 同内容文件：`reports/workflow_runs/wf_20260703_stock_first_002837_invic/data/raw/annual_reports/szse_annual_report_002837_2026-04-21.pdf`，SHA256 相同。
- 决策：两条 evidence ID 是 provenance alias，不是两份独立证据；只可作为 `business_disclosure` candidate，不能自动生成 accepted record。
- 当前官方摘要可支持产品线 clue 和部分公司/业务事实；液冷收入占比、毛利率、利润贡献仍为 `MISSING_DISCLOSURE`。
- workflow-local manifest 的 `data/raw/...` 路径只有按 workflow run 根解析才存在，按 repo root 解析不存在；此路径口径差异保持为维护 TODO，未静默改写历史 manifest。

## source_request_refresh

- 正式 builder：`.agents/skills/evidence-ingest/scripts/build_r5_evidence_request_queue.py`。
- 本轮重建到系统临时文件后，与现有 `R5_evidence_request_queue.yaml` 的 SHA256 完全一致：`04594CC390164770215D9BE69C384766838689CBA349ECE8A0037EB5852225F5`。
- 因字节一致，正式 queue 未被无意义重写；五类核心 inventory 均链接到现有 request_id。
- `valuation_inputs` 没有伪造为原始 evidence request；inventory 链接其 market/peer/forecast 依赖请求，后续仍需授权 reviewer 完成 derived-input 审核。

## quality_review

`quality-review` 按 G1、证据锚点、reviewer、TODO、fixture 和 no-advice 边界给出以下 active issues：

| issue_id | severity | gate_id | target_artifact | description | fix_owner_skill | next_action | status |
|---|---|---|---|---|---|---|---|
| `B5-G1-BUSINESS-001` | high | G1 | `business_disclosure` dropzone | 无真实 accepted record、reviewer/reviewed_at；现有官方摘要不足以覆盖关键分业务披露 | `evidence-ingest` + authorized reviewer | 归档/定位充分官方披露，人工审核后按模板写入 record | open |
| `B5-G1-MARKET-001` | high | G1 | `market_snapshot` dropzone | 无 dated、reviewed、evidence-anchored market record | `evidence-ingest` + authorized reviewer | 提供离线可归档 snapshot，核对价格/股本/口径/时区 | open |
| `B5-G1-PEER-001` | high | G1 | `peer_snapshot` dropzone | 无 reviewed peer set、纳入排除理由和同口径指标 | `evidence-ingest` + authorized reviewer | 提供可比公司来源、期间、单位、会计口径和限制 | open |
| `B5-G1-FORECAST-001` | high | G1 | `forecast_assumptions` dropzone | 核心 assumptions 全为 pending/TODO，未绑定 accepted evidence/metric 和 reviewer | `stock-deep-dive` + authorized reviewer | 在基础证据就绪后审核场景、方法、依赖和敏感性 | open |
| `B5-G1-VALUATION-001` | high | G1 | `valuation_inputs` dropzone | 缺估值日期、股本、净债务桥、方法资格和 reviewer | `stock-deep-dive` + `company-valuation` + authorized reviewer | 完成 market/peer/forecast/business 依赖后再审核 valuation input | open |
| `B5-G1-PROVENANCE-001` | medium | G1 | evidence manifests | 同内容年报有两个 evidence ID/路径，workflow-local raw path 口径不符合 repo-root 解析 | `evidence-ingest` | 保留 alias/duplicate 关系并在后续 manifest 维护中统一路径语义 | open |

No-advice 检查通过；inventory、queue 和 readout 未包含买卖、仓位、时点或保证收益指令。

## files_added

- `scripts/build_r5_bundle5_real_input_inventory.py`
- `tests/test_r5_bundle5_real_input_inventory.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_real_input_inventory.yaml`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_dropzone_validation_initial.json`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/handoffs/06_to_evidence-ingest_bundle5_real_input_inventory.md`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/handoffs/07_to_quality-review_bundle5_real_input_inventory.md`
- `reports/p1_6/R5_BUNDLE_5_1_REAL_INPUT_INVENTORY_READOUT.md`

## files_modified

- `config/r5_bundle5_expected_artifacts.yaml`：登记 Card 5.1 实际新增的 focused inventory builder；未改变 gate 或 future-card 范围。
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_queue.yaml`：fresh 重建结果与现文件字节一致，因此实际 diff 为 0。

## commands_run

- `git status --short`
- `git diff --check`
- `.\\.conda\\investment-system\\python.exe .agents/skills/evidence-ingest/scripts/build_r5_evidence_request_queue.py --plan reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_plan_from_gaps.yaml --out $env:TEMP/R5_bundle5_evidence_request_queue_refresh.yaml`
- `Get-FileHash` 比较正式 queue 与 fresh 临时 queue。
- `.\\.conda\\investment-system\\python.exe scripts/validate_r5_reviewed_input_dropzone.py --root data/reviewed_inputs/wf_20260703_stock_first_002837_invic --json reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_dropzone_validation_initial.json`
- `.\\.conda\\investment-system\\python.exe scripts/build_r5_bundle5_real_input_inventory.py --repo-root . --workflow-id wf_20260703_stock_first_002837_invic --stock-code 002837 --dropzone-root data/reviewed_inputs/wf_20260703_stock_first_002837_invic --output reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_real_input_inventory.yaml`
- `.\\.conda\\investment-system\\python.exe -m pytest -q tests/test_r5_bundle5_real_input_inventory.py tests/test_validate_r5_reviewed_input_dropzone.py tests/test_build_r5_evidence_request_queue.py --tb=short -p no:cacheprovider`
- `.\\.conda\\investment-system\\python.exe -m py_compile scripts/build_r5_bundle5_real_input_inventory.py tests/test_r5_bundle5_status_baseline.py tests/test_r5_bundle5_real_input_inventory.py`
- `.\\.conda\\investment-system\\python.exe -m pytest -q --tb=short -p no:cacheprovider`
- 对解压包 `repo_patch/codex_tasks/r5_after_bundle4/**` 与已安装任务目录逐文件执行 SHA256 比对。

## exit_code

- pre-card git status / diff check: `0`
- source-request queue refresh: `0`
- dropzone validator: `0`（空目录 pass，不代表 evidence gate pass）
- inventory builder: `0`（清点成功，业务状态为 blocked）
- first focused pytest: `1`，`16 passed, 1 failed`；fixture-origin 边界正则未把空格识别为 token boundary。
- focused pytest rerun after owned fix: `0`，`17 passed in 0.27s`。
- focused Python compile: `0`。
- full repository pytest: `0`，`458 passed, 2 skipped in 19.87s`。
- installed task-package hash comparison: `0`，`checked=14 failed=0`。
- final truthfulness and diff check: `0`。

## stdout_or_stderr_summary

- queue builder: `status=planned requests=10 no_live_api=true`；fresh/current SHA256 一致。
- dropzone validator: `pass checked_files=0 accepted=0 accepted_degraded=0 pending=0 rejected=0 failed=0`。
- inventory builder: `status=blocked_source_gapped core=0/5 records=0 promotion_allowed=false sample_quality=false p2=false`。
- first focused pytest 的失败由测试成功发现；修复 token boundary 后，synthetic physical evidence anchor 可接受、fixture evidence 必须拒绝的合同均通过。
- full repository pytest: `458 passed, 2 skipped in 19.87s`。
- 补丁内 14 个 task-package 文件与安装目录逐文件 SHA256 一致；最新 zip SHA256 为 `57691F7A7174224172448F6626120384E1F262AF09B92612C41DED72D39077BC`。
- real workflow `workflow_state.yaml`、canonical registries、pilot/gate/render 产物保持只读，符合 pre-Card-5.5 边界。

## artifact_evidence

- inventory_status: `blocked_source_gapped`
- inventory: `line_count=208 sha256=C2F3B9C3A7460A076B4B58086D853F73BA30A9BC14105BC3420B3DB39DAF3B88`
- dropzone_validation: `line_count=17 sha256=72A0C6831AE74988D4D80CD3B33175C90E8354CCE2B3765D0BF33F2F7A45C6A7`
- source_request_queue: `line_count=227 sha256=04594CC390164770215D9BE69C384766838689CBA349ECE8A0037EB5852225F5`
- reviewed_core_coverage: `checked=5 accepted=0 missing_or_invalid=5`
- optional_coverage: `checked=1 accepted=0 blocking=false`
- provenance_aliases: `checked=1` duplicate-content group；不计为独立 evidence。
- installed_task_package: `checked=14 failed=0`。
- full_repository_pytest: `458 passed, 2 skipped`。

## blockers

- 五类核心 reviewed input 均缺少可验证 accepted record；G1 Evidence Gate fail。
- reviewer 身份和 reviewed_at 不能由 Codex 伪造。
- Card 5.2 及后续 Cards 5.3–5.8 不得执行。

## known_todos

- owner=`evidence-ingest` + authorized reviewer；severity=`high`：补齐 `business_disclosure`。
- owner=`evidence-ingest` + authorized reviewer；severity=`high`：补齐 `market_snapshot`。
- owner=`evidence-ingest` + authorized reviewer；severity=`high`：补齐 `peer_snapshot`。
- owner=`stock-deep-dive` + authorized reviewer；severity=`high`：在基础证据就绪后补齐 `forecast_assumptions`。
- owner=`stock-deep-dive` + `company-valuation` + authorized reviewer；severity=`high`：补齐 `valuation_inputs` 和方法资格。
- owner=`evidence-ingest`；severity=`medium`：维护同 hash annual-report alias 与 workflow-local path 语义。

## next_card

- blocked；不进入 Card 5.2。

## next_recommended_patch

- 不是继续执行实现卡，而是完成最小 reviewed-input remediation：由授权 reviewer 提供并审核五类真实输入；输入到位后从 Card 5.1 fresh 重跑，不直接跳到 promotion。
