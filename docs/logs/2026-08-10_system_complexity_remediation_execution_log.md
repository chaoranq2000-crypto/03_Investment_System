# 系统复杂度修正执行日志：Phase 0–7

## 1. 记录信息

| 字段 | 内容 |
|---|---|
| date | `2026-08-10`–`2026-08-11`（Asia/Shanghai） |
| scope | 系统复杂度修正 Phase 0–6 的实现与 Phase 7 验证；Research 与 Investment Review 分支分别实施 |
| status | `completed`；达到 bounded engineering stop，不等同于 Review 人工产品验收、分支合并或用户风险参数确认 |
| research_baseline | `origin/main@d21aa5a9fc4e0a8aaf77ad4d6c7ba3dd814b79d8` |
| review_baseline | `codex/portfolio-tracker@f56854bfdefce9ce40826e1249446a4dba68276d` |
| implementation_branch | Research：`codex/system-simplification-plan`；Review：`codex/investment-review-simplification` |
| changed_paths | Review 的产品边界、skill/policy、周期报告/叙事、API/UI、行为观察边界与测试；Research 的 AGENTS/workflow/spec/policy/skills、状态 schema/validator、pointer/navigation、评分与生成器、adapter、CI/测试隔离及文档 |
| open_risks | `C-HUMAN-005` 未决定；证据耦合的主动 advice 未自动启用；两个实施分支尚未合并或部署；旧 worktree/历史资产未清理 |

本日志只记录已经发生的实施与验证，不是新的 policy、Gate、全局状态或长期运行契约。

## 2. Phase 0 已完成的基线工作

- 从产品线最新 committed tip `f56854b` 建立新的干净集成工作树，没有修改脏的 Portfolio、completion、reviewability 或 periodic-v1 工作树。
- 复核 committed 祖先链：`c3e2966 → c2db0d9 → aac8290 → f56854b`；没有把三个阶段分支分别合并。
- 旧阶段快照只作只读参照；没有 reset、clean、stash 或删除。
- 记录 Research `origin/main` 与产品线从 `08acbf9` 分叉，禁止整树合并。
- 对正式 Portfolio 数据库执行只读完整性检查：`PRAGMA quick_check=ok`，且校验前后内容指纹不变。
- 修改前周期报告、叙事和建议定向基线为 `21 passed`。

## 3. Phase 1 已实施的行为修正

### 3.1 产品边界

- `AGENTS.md` 直接定义 Research、Portfolio、Investment Review 三个产品的职责，不再依赖“全局 no-advice + Review 例外”或“全局允许建议”的覆盖链。
- Research 保持 no-advice；Portfolio 只负责账务和可验证事实。
- 普通 Investment Review 周期报告默认 `observation_only`。缺少明确 advice 请求、用户投资期限、风险预算或仓位约束时：
  - `action=null`；
  - `target_position=null`；
  - 只输出事实、风险观察、缺失输入与待确认问题。

### 3.2 删除机械默认值

- 删除 `top_weight > 20%` 或 `cash_weight < 5%` 自动导出 `reduce` 的活动逻辑。
- 删除缺少用户输入时自动生成的 5%–10%、8%–12%、12%–18% 等目标区间。
- 删除现金 5%、最大单票 20%、前三大 50% 在 reader narrative 中决定“重要风险”的隐藏阈值。
- 删除 `top_position_weight > 20%` 自动形成 `HIGH/MODERATE` 集中度标签的活动逻辑；报告仍保留现金、最大单票和前三大权重事实。

### 3.3 显式 advice 与历史兼容

- 单份报告只有同时收到 `review_mode=advice`、用户确认的投资期限、风险预算和目标区间，才形成动作；范围和期限只使用用户值，标记 `decision_basis=user_policy_trigger`。
- 自动/批量 advice 没有启用。结构化上下文目前不能可靠表达证据对动作方向的支持或反对，因此没有为了满足流程再增加方向评分或元规则。
- 无 `mode` 的旧 action 报告保持原始 payload 不变；API 投影、前端和 Markdown 将其标为 `historical_snapshot` / “历史建议快照，非当前有效建议”。
- 既有 619 份报告、P8/P9 样稿、P10 阶梯实验和 `C-HUMAN-005` 均未改写。

## 4. 验证结果

| 验证 | 结果 |
|---|---|
| Python 定向行为、叙事、周期报告与 API 投影 | `28 passed` |
| 前端 Vitest | `3 files / 28 tests passed` |
| 前端生产构建 | Vite build passed；只更新 tracked `app.js`，无 CSS 实质变化 |
| 文档漂移、Python 编译、Git diff | `check_doc_drift.py`、`py_compile`、`git diff --check` 通过 |
| 活动代码隐藏阈值搜索 | 目标文件中无 5/12/20/50 默认动作阈值或 HIGH/MODERATE 集中度分类匹配 |
| 正式账本实样 | 用正式库最新可用组合数据生成报告：`observation_only`、无动作值、无目标仓位，Markdown 明示未生成交易动作 |
| 正式账本完整性 | 实样前后内容指纹不变，`quick_check=ok` |
| 较大产品回归（早期批次） | `159 passed, 1 deselected, 2 failed`；两项均在后续被确认是固定日期早于临时 sidecar 实际导入时刻的测试夹具失效，不是产品逻辑失败 |

后续对两个失败做了独立诊断：

1. `test_v2_operation_checkpoint_projects_six_axes_and_paired_perspectives` 的固定 `2026-07-30` cutoff 早于临时 sidecar 的实际 `first_ingest.observed_at`；
2. `test_v2_automation_binds_perspective_anchor_and_carries_system_limitation` 的固定 automation clock 也早于该观测时间。

测试现从本次临时 sidecar 的实际观测时间推导 cutoff/clock；原两项及相邻用例 `6 passed`。生产时间边界、正式 SQLite 和报告逻辑均未改变。

## 5. Phase 2 已实施的研究输出修正

### 5.1 Scorecard 缺失语义

- 确认 `config/scoring_frameworks.yaml` 是唯一活动 stock/segment scorecard 契约；当前无总分、权重或 `deep_watch` 自动映射消费者。
- 修正契约中 `0=no_evidence_or_not_applicable` 的混淆：0 只表示有证据支持的极弱评估；只有 `config/scoring_frameworks.yaml` 定义的占位前缀（包括 TODO、MISSING、LOW_CONFIDENCE、UNVERIFIED 与 NOT_APPLICABLE 及其现有变体）时使用 `score: null` 和 `score_type: unscored`。
- 数字分数保留为 `score_type: analyst_judgment`，必须至少有一个非占位证据；本轮没有发明新的不确定性分数。
- 当前 002837、300731 和 `ai_server_liquid_cooling` 三份未带日期评分卡已更新；TODO-only 数字违规从 10 项降为 0。
- `final_priority` 保留，但增加 `final_priority_type: research_priority` 和 `priority_basis: analyst_judgment_not_score_aggregation`；没有新增总分或阈值。
- 同步修正唯一 P1 builder 的结构漂移：segment 从 6 维、stock 从 4 维补齐到当前 8/9 维；通过临时目录重放验证，没有直接运行会覆写大量 P1 文件的 `main()`。
- `RESEARCH_WORKFLOW.md`、segment/stock research、compare-segments/compare-stocks 和 quality-review 只引用上述三个语义，没有新建 scorecard workflow、Gate、审批层或权重表。

### 5.2 披露缺失不再伪装成 Kill Switch

- 审计确认 `kill_switches` 没有 schema、validator、运行时消费者、“连续两期”计数或 thesis 状态转换；它是旧 P1 可见文案，不是真正执行机制。
- 从两份当前 stock scorecard 与 P1 builder 删除该字段，不创建新 Kill-Switch schema。
- 复用现有 `config/watchlist.yaml -> triggers`：连续未找到披露只触发补证与重评，不等同命题失效。Watchlist 语义变更已写入现有 `decisions/watchlist_changes.md`，未新建登记系统。
- 后续报告生成不再因“未披露”自动维持或下调 exposure score。若长期缺失披露影响分析者置信度或评分，必须明示时间预期、披露边界和证据覆盖；不得把缺失写成业务不存在，真正 thesis invalidation 仍需要反面事实。
- 当前 canonical 002837 run 原本已使用正确语义：未披露是 `unknown/method_unavailable`、`blocks_current_goal=false`，outcome 仍为 `accepted_with_todos`；本轮未改写该 run。

### 5.3 Reader rubric 默认路由

- 全面检查 82/45 分、字数、引用配额和关键词比例的定义与 import。
- 当前 `RESEARCH_WORKFLOW.md`、`WORKFLOW_ORCHESTRATION_SPEC.md`、research-orchestrator、stock-deep-dive 和 quality-review 都明示 Bundle11R–16R / R5-G1–G11 不在普通默认路由。
- 普通 `src/qa/stock_report_quality_review.py` 只检查证据、claims/metrics、业务暴露、forecast/valuation、technical date、no-advice 与 backflow，不读取 Reader rubric。
- 唯一 import 仍是显式 `run_r5_bundle10r_reader_quality_gate.py`；历史 config、scripts、fixtures 和 tests 保留。因此本轮不对 Reader 部分写代码，也不以新 rubric 取代它。

### 5.4 Phase 2 验证

| 验证 | 结果 |
|---|---|
| P1.5 评分契约、当前样本、临时生成器重放 | `16 passed` |
| P0/P1/P1.5、segment-stock backflow、002837 policy refresh、active control plane、V1 completion | `63 passed` |
| 结构检查 | YAML parse、`py_compile`、`check_doc_drift.py`、`git diff --check` 通过 |
| 当前三份 scorecard | TODO-only numeric violations=`0`；numeric-without-type=`0`；`kill_switches`=`0` |
| Research 全量 pytest | 首次 10 分钟命令窗未完成；随后用完整时间窗自然跑完：`981 passed, 2 skipped in 834.56s` |

三份当前 2026-07-01 P1 报告只定点更新了评分展示或缺失披露解释，并写明 2026-08-10 语义修正；原始证据快照、report_date 和其他报告结论未改变。`reports/workflow_runs/**`、历史 R5/Bundle 配置和历史 Reader 成绩均未改写。

## 6. Phase 3：current pointer 与状态职责

- `config/r5_readout_canonical_index.yaml.current_runs` 只保留 `workflow_id`、`state_path` 与 `readout_path`；删除手写 `status` 副本。
- README 与 `docs/index.md` 只链接该 pointer，不冻结具体 run ID/status；历史 Markdown index 明确降为 R5/Patch/Bundle 历史目录。
- `DOC_OWNERSHIP_MATRIX.md` 增补 cross-run pointer owner；没有新建第三个 index 或同步 Gate。
- 未来普通 run 模板不再写项目/发布/P2 的跨层布尔值、可派生的自动报告质量布尔值或嵌套 final-review decision；validator 对旧字段只做一致性兼容。
- 固定 policy-refresh/replay writer 与当前 hash-bound run 保持字节不变；`reports/workflow_runs/**` 无 diff。

## 7. Phase 4–5：核心事实源收缩与普通路径解耦

- Research `AGENTS.md` 直接定义 Research / Portfolio / Investment Review 三产品边界，并把历史多层删除治理压缩为可执行的安全边界：需明确授权、一次一个 literal file、禁止递归/通配符/批量删除。
- `RESEARCH_WORKFLOW.md` 成为 ordinary run、G0–G10、TODO/backflow/outcome 的 owner；orchestration spec 只负责投影和运行时；quality policy 只保留质量原则、人审边界和 owner 链接。
- workflow state schema/reference 负责字段合同；kernel/spec/policy/skills 不再复制四个完成布尔、final-review 字段真值表或 issue outcome 表。
- orchestrator、quality-review、stock-deep-dive、evidence-ingest、company-valuation 等按任务渐进加载 reference；普通路径不再枚举 Bundle11R–16R、R5-Gx、Reader/Night 或长期 Goal。
- 显式 capability-local evaluator 仍可调用，但只返回映射到 G0–G10 的 scoped issue，不能写 canonical outcome。
- adapter 新运行使用通用 `adapter_run_*` / `report_pdf_run_*` ID；对已有 legacy ledger ID 只做兼容复用。项目阶段 owner 已由 P1.5 对齐到 P1.6。

## 8. Phase 6：历史工程隔离

- `test_r5_v1_historical_baseline_manifest.py`、`test_r5_v1_historical_cleanup_manifest.py` 与 `test_r5_v1_replay_002837.py` 标记为 `legacy_compatibility`。
- `pyproject.toml` 默认排除该 marker；标准 CI 保留活动 routing-retirement 检查和默认全套，不再直接运行三个冻结历史文件。
- 新增仅 `workflow_dispatch` 的手动历史兼容 workflow；显式套件 30 项全部通过。
- 历史工具/测试读取其 package baseline 与 decoupling checkpoint，不再冻结当前 `AGENTS.md`，也不再要求当前 CI 永远包含旧 V-006 三件套。
- 隔离已解决默认测试和认知成本，本轮没有移动或删除任何历史文件、旧 worktree、fixture 或 Git blob。

## 9. Phase 7 验证记录

| 验证 | 结果 |
|---|---|
| Research 活动语义定向集 | `82 passed` |
| Research 默认全套 | `949 passed, 2 skipped, 30 deselected in 90.03s` |
| Research 手动历史兼容套件 | `30 passed in 398.18s` |
| skills / 文档 / 结构 | 8 个 skill `quick_validate` 通过；`check_doc_drift.py`、8 份 YAML parse、`py_compile`、`git diff --check` 通过 |
| workflow 历史不可变 | `reports/workflow_runs/**` 无 diff |
| Review 前端 | `3 files / 28 tests passed`；Vite production build 通过 |
| 正式 Portfolio SQLite | 内容指纹前后不变；只读 `quick_check=ok` |
| Review 宽回归 | P2F 最终边界修正后：`1352 passed, 1 skipped, 640 deselected in 523.50s` |

Review 首轮宽回归为 `1344 passed, 1 skipped, 8 failed, 640 deselected`。其中七项揭示 portfolio tip 已存在的边界泄漏：一次“允许建议”的全局修改同时移除了行为假设、观察协议和动机层的 direct-advice 检查。进一步调用面复核还发现 P2F episode interpretation/model/human revision 本身没有 `review_mode`、风险预算或用户策略输入，却把 `no_advice` 写成 false。最终修正恢复一个共同的 P2F/behavior/observation no-advice policy、schema 与 renderer；只有独立的 periodic recommendation 路径在满足 advice boundary 时可给建议，没有新增权限 registry 或例外表。剩余一项是 Windows CRLF 使冻结 schema 原始字节哈希不同；测试改为规范化换行后核对同一个 SHA-256，schema 与预期哈希均未修改。

## 10. 停止点与未代替用户决定的事项

- 普通 Review 已停止制造动作与仓位；行为观察/动机层也不再因推荐产品存在而混入建议。
- 精确回撤架构、默认现金/仓位参数仍停在 `C-HUMAN-005`；本轮没有代替用户选择。
- 证据如何参与主动 advice 方向尚未有诚实的结构化输入。自动/批量 advice 保持关闭；后续应从一次真实、显式的 advice 请求出发，而不是新增方向分数或元规则。
- 本日志收口时两个实施分支尚未 merge 或部署；后续 commit、push 和 PR 由 Git/GitHub 记录。没有清理任何旧 worktree 或历史产物。
- 本日志记录到 bounded remediation 的工程停止点，不创建 `system_simplified=true`、新 Gate、复杂度分数或长期反递归治理程序。
