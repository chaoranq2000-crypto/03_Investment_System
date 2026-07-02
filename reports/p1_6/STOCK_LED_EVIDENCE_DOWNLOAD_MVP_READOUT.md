# P1.6 Stock-led Evidence Download MVP Readout

> 本 readout 记录本轮 `stock_led_evidence_download_patch.zip` 的应用、项目化调整和验收结果。本轮不进入 P2，不生成买入/卖出/持有建议。

## 1. 修改文件清单

| 文件 | 状态 | 说明 |
|---|---|---|
| `.agents/skills/evidence-ingest/SKILL.md` | modified | 增加 stock evidence plan、official disclosure、structured API pull 的证据层边界；保留 B1 兼容锚点。 |
| `.agents/skills/evidence-ingest/references/adapter_notes/tushare.md` | modified | 将结构化快照 raw 目录统一为 `data/raw/market_data/`。 |
| `.agents/skills/evidence-ingest/references/ingest_modes.md` | modified | 将 `structured_api_pull` raw 输出路径统一为 `data/raw/market_data/`。 |
| `.agents/skills/evidence-ingest/references/storage_manifest_contract.md` | modified | 去除补丁包里的新 raw bucket，保持当前仓库目录规则。 |
| `.agents/skills/research-orchestrator/references/skill_routing_matrix.md` | modified | 增加 stock-first / evidence download MVP 路由。 |
| `.agents/skills/stock-deep-dive/SKILL.md` | modified | 增加 B5-lite 契约：company identity、evidence plan、business skeleton、linked segments、segment exposure、backflow。 |
| `.agents/skills/segment-company-mapping/SKILL.md` | modified | 增加 B4-lite 契约；修复 YAML frontmatter 引号兼容。 |
| `.agents/skills/quality-review/SKILL.md` | modified | 增加 B6-lite stock gates 和 issue schema；保留 P0/P1 测试要求的中文 checklist。 |
| `src/ingest/evidence_io.py` | modified after overlay | 将 `metrics_draft.csv` 字段常量对齐当前仓库现有 schema。 |
| `src/ingest/official_disclosure_pull.py` | modified after overlay | 将官方披露 raw 归档目录对齐 `annual_reports` / `announcements`。 |
| `src/ingest/structured_api_pull.py` | modified after overlay | 将结构化快照 raw 目录对齐 `market_data`，metric candidates 对齐现有 schema。 |
| `tests/test_stock_led_evidence_download.py` | modified after overlay | 将测试断言同步到当前仓库目录规则。 |

## 2. 新增文件清单

| 文件 | 说明 |
|---|---|
| `.agents/skills/evidence-ingest/assets/stock_evidence_plan_template.yaml` | 个股证据计划模板。 |
| `.agents/skills/evidence-ingest/references/stock_evidence_plan.md` | stock evidence plan 契约。 |
| `.agents/skills/evidence-ingest/references/official_disclosure_download.md` | 官方披露下载/登记契约。 |
| `.agents/skills/evidence-ingest/references/structured_api_pull_runner.md` | 结构化 API / 本地 fixture 快照契约。 |
| `docs/plans/P1_6_WORKFLOW_BUILDOUT_PLAN.md` | 调整后的 P1.6 阶段计划：先 stock-led MVP，再 B2/B3。 |
| `src/ingest/evidence_io.py` | evidence/metric/log CSV、hash、immutable copy 等公共工具。 |
| `src/ingest/stock_evidence_plan_runner.py` | 生成 `stock_first_closed_loop` 个股证据计划。 |
| `src/ingest/official_disclosure_pull.py` | URL 下载或本地官方披露登记；失败可 metadata-only。 |
| `src/ingest/structured_api_pull.py` | 本地 CSV/JSON 结构化快照登记并生成 metric candidates。 |
| `tests/test_stock_led_evidence_download.py` | 离线测试：结构化快照、官方披露登记、不写报告。 |
| `reports/p1_6/STOCK_LED_EVIDENCE_DOWNLOAD_MVP_READOUT.md` | 本 readout。 |

## 3. Stock-led debug 是否已跑

| 项目 | 状态 | 说明 |
|---|---|---|
| B1.5 evidence download layer offline debug | PASS | `tests/test_stock_led_evidence_download.py` 使用临时目录验证了结构化 CSV fixture 和本地官方披露登记。 |
| Full `stock_first_closed_loop` T0-T10 debug | NOT_RUN | 本轮未创建正式 `reports/workflow_runs/wf_...stock_first...`，也未重新生成 002837 个股报告。 |
| Existing 002837 sample assets | VERIFIED_EXISTING | 已确认现有 `reports/stocks/002837_invic/2026-07-01_stock_deep_dive.md`、`segment_exposure.yaml`、`evidence_map.md` 存在；本轮未覆盖。 |

结论：本轮通过的是 **stock-led evidence download MVP / B1.5 证据获取层**，不是完整 stock-led 研究闭环验收。

## 4. Manifest / Metrics / Ingest Log 新增情况

| 目标 | 本仓库正式文件 | 新增情况 |
|---|---|---|
| `data/manifests/evidence_manifest.csv` | exists | 本轮未向正式 manifest 追加调试行；离线测试在 pytest 临时目录验证新增 manifest row。 |
| `data/manifests/metrics_draft.csv` | exists | 本轮未向正式 metrics draft 追加调试行；已修复脚本字段顺序，避免未来追加时与现有 schema 错位。 |
| `data/manifests/ingest_runs.csv` | not present before run | 本轮未在正式仓库创建；离线测试验证了 ingest log JSON 输出。 |
| `data/processed/logs/*__ingest_log.json` | not changed | 本轮未写正式 ingest log；离线测试验证可生成。 |

## 5. Stock / Exposure / Quality 产物状态

| 产物 | 状态 | 路径 / 说明 |
|---|---|---|
| stock evidence plan contract | ADDED | `.agents/skills/evidence-ingest/references/stock_evidence_plan.md` |
| stock evidence plan runner | ADDED | `src/ingest/stock_evidence_plan_runner.py` |
| stock-deep-dive B5-lite contract | ADDED_CONTRACT | `.agents/skills/stock-deep-dive/SKILL.md`；未生成新 stock report。 |
| existing stock report sample | EXISTS | `reports/stocks/002837_invic/2026-07-01_stock_deep_dive.md` |
| segment exposure sample | EXISTS | `reports/stocks/002837_invic/segment_exposure.yaml` |
| segment-company-mapping B4-lite contract | ADDED_CONTRACT | `.agents/skills/segment-company-mapping/SKILL.md`；未新增 exposure change note。 |
| quality-review B6-lite stock gates | ADDED_CONTRACT | `.agents/skills/quality-review/SKILL.md`；未新增 stock-led quality issue list。 |

## 6. Issues

| severity | issue | status | next action |
|---|---|---|---|
| high | 补丁覆盖后曾丢失旧测试锚点 / YAML frontmatter 冒号未加引号 | fixed | 已保留兼容锚点并通过全量测试。 |
| high | 结构化脚本原始 `metrics_draft.csv` 字段与仓库现有 schema 不一致 | fixed | 已对齐现有表头，避免正式运行时列错位。 |
| medium | full stock-led T0-T10 debug 尚未跑 | open | 下一步用 002837 创建 workflow run，执行 evidence plan、report/mapping/review/readout。 |
| medium | real Tushare/Baostock adapters 尚未实现 | accepted_todo | 当前只支持 local CSV/JSON fixture；真实 API 接入留到后续。 |
| medium | official disclosure runner 只登记/归档，未解析页码、表格或 claim candidates | accepted_todo | 后续接入解析层，不能直接形成业务暴露 claim。 |
| low | 根目录补丁包 `stock_led_evidence_download_patch.zip` 仍为用户提供的未跟踪文件 | open | 是否保留由用户决定；本轮不删除。 |

## 7. Verification

| command | result |
|---|---|
| `conda run -p .\.conda\investment-system python -m pytest tests/test_stock_led_evidence_download.py -q` | PASS, 2 passed |
| `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 conda run -p .\.conda\investment-system python -m pytest -q` | PASS, 30 passed |
| `conda run -p .\.conda\investment-system python .agents\skills\research-orchestrator\scripts\validate_workflow_state.py .agents\skills\research-orchestrator\assets\workflow_state_template.yaml` | PASS, OK |
| `rg "data/raw/financial_data|data/raw/official_disclosure"` | PASS, no remaining matches in new script/reference/test surface |

## 8. Next Step Decision

不进入 P2，也不建议立刻进入 B2 `segment-research` 完整契约。

下一步应继续 **B5/B4/B6-lite + stock-led debug**：

1. 用 `002837` 创建正式 `stock_first_closed_loop` workflow run。
2. 生成 `stock_evidence_plan.yaml`。
3. 用已有官方年报和本地结构化 CSV 快照跑一次正式 evidence-ingest 登记，必要时只新增明确标记为 debug / draft 的 manifest rows。
4. 让 stock-deep-dive 消费 evidence package，明确哪些现有 002837 报告可复用、哪些必须重生成。
5. 让 mapping 接住 `segment_exposure.yaml`，输出 exposure update 或 `exposure_change_note.md`。
6. 让 quality-review 输出标准 issue list。
7. 由 research-orchestrator 输出 workflow readout，状态只能是 `accepted` / `accepted_with_todos` / `needs_fix` / `blocked` 之一。

只有 full stock-led debug 至少达到 `accepted_with_todos` 后，才进入 B2 `segment-research` 完整细分契约。
