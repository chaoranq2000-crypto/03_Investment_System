---
schema_version: "1"
task_id: "investment_review_periodic_v1"
package_version: "1"
status: "active"
source_baseline: "7df75562eb7c7123ff066406f92fd6b844be994b"
execution_branch: "codex/investment-review-periodic-v1"
package_path: "docs/codex_tasks/investment_review_periodic_v1"
created_at: "2026-07-28T10:57:04+08:00"
language: "zh-CN"
activated_at: "2026-07-28T03:22:55+00:00"
---
# 周期投资复盘产品 V1 执行合同

> 激活后 `status` 变为 `active`。本文件是当前阶段可修订的唯一执行合同；若用户方向或仓库事实变化，在同一文件内修订并记录原因。

## Context capsule

- **Problem or opportunity:** 当前投资复盘产品已经具备真实账本同步、Trade Episode、事实复盘、操作检查点、行情上下文、API/UI 和进程内自动化基础，但产品对象仍是按 `single/weekly/monthly` 筛选的逐 episode 事实报告。用户无法直接看到组合与单个标的的自然日、自然周、自然月周期报告；缺少 Decision 时仍没有自动交易动机分析；建议边界虽然已经放开，但周期建议生成器尚未建设。
- **Why this stage exists:** 用户已固定目标：以最少新增结构完成可直接阅读的周期复盘产品；无决策记录时自动推断动机；报告提供个性化买入、卖出、持有、加减仓、退出和仓位建议；不继续扩建 P2G/P2H、复杂画像或重型审计。
- **Relevant current state:** 执行工作树为 `C:\Projects\03_Investment_System_periodic_review_v1`，分支为 `codex/investment-review-periodic-v1`，执行基线为 `7df75562eb7c7123ff066406f92fd6b844be994b`。提交 `9e2b15d` 与 `4757d02` 已形成首版 P1 日报和工程检查点，但用户未接受该样本：标的操作复盘缺少股票中文名称，动机分析过于机械，并持续强调已经由用户修复的手续费缺失。2026-07-28 用户在仓库外部更新了正式账本的手续费逻辑并完成历史回填；回执为 `C:\Projects\03_Investment_System\data\db\portfolio_fee_backfill_20260728T062640Z.json`，修订时正式库 SHA-256 为 `6207d15cc61cffd963cc8154a1b9af2ddae56ae11efe9a26116f7792e6ffb057`。用户随后明确确认本合同新增的四层复盘框架。最早尚未证明的 outcome 因而仍是修订后的 P1，而不是 P2。
- **Authoritative sources:** 根目录 `AGENTS.md`；`.agents/skills/investment-review/SKILL.md`；`docs/plans/INVESTMENT_REVIEW_IMPLEMENTATION_PLAN.md`；本合同与同目录 `START_HERE.md`；直接相关源代码与真实只读数据库。旧 `docs/playbooks/INVESTMENT_REVIEW_P2*.md` 仅是历史实现参考，冲突时不控制本 V1。
- **Known gaps and external dependencies:** 正式库当前没有可靠的 Decision 覆盖；首版 P1 只使用了机械化的操作角色、既往收盘和仓位信息，尚未形成基本面与估值、大盘与板块、技术与趋势、仓位与执行四层上下文；真实行情、行业映射、已审查基本面/估值证据与历史现金快照的一致性必须在执行时检查，不能假定。P1 样板的人工阅读结论必须由用户给出；生产发布、远端推送、系统级调度和订单执行均未授权。
- **Instruction precedence:** 当前适用的 `AGENTS.md` 高于本合同；`investment-review` skill 高于旧 playbook；本合同高于临时执行判断。无先前聊天、memory、其他任务包或未写入决定可以改变本合同。

This capsule is self-contained. No prior chat, memory, or unstated decision is authoritative.

## Objective and completion semantics

### Fixed objective

在保持正式 portfolio SQLite 只读、不开通券商或订单执行的前提下，完成一个轻量的周期投资复盘产品：

1. 生成组合与单个标的的日报、周报、月报六类周期报告；
2. 报告主体包含周期表现、持仓/现金/风险变化、基本面与估值、大盘与板块、技术与趋势、仓位与执行、动机分析和个性化交易建议；
3. 没有 Decision 时仍从操作时点可用信息生成 `system_inference` 动机假设、依据、替代解释、定性可信度和缺失信息；
4. 每份报告基于报告截止时点信息给出直接的买入/卖出/持有/加减仓/退出建议及建议仓位或区间，并列出依据、期限、风险和失效条件；
5. 用户从一个报告中心直接浏览最新与历史报告，系统支持幂等补跑和进程内周期生成；
6. 不新增 P2G/P2H、行为画像、复杂评分、复杂风险模型、新审计协议或与周期报告无关的功能。

### Confirmed reader-facing review framework

用户于 2026-07-28 明确确认以下框架。该确认是修订 P1 的产品指导，不是 `accept_p1_sample_and_continue`，不得据此进入 P2。

1. **标的身份:** 标的标题、操作列表和建议区域统一显示“股票中文名称（代码）”。源数据已有名称时不得只显示代码；确实缺失时显示 `MISSING_INSTRUMENT_NAME`，不得静默省略。
2. **基本面与估值:** 回答“为什么应当持有、当前价格是否合理”。优先复用仓库已有且在报告截止时点可用的已审查财务、业务、估值、催化剂与风险证据；普通周期报告不另起完整个股深度研究，不用未来披露回填历史判断。日报只写新增变化或明确写“未发现新增可审查变化”，不得重复固定公司介绍。
3. **大盘与板块:** 回答“表现来自整体市场、所属板块还是个股自身”。在可用时给出相关基准、行业/板块表现和个股相对表现，用于环境说明与归因；行业映射或行情缺失时明确显示缺口，不得猜测板块归属或把共同涨跌直接写成用户动机。
4. **技术面与趋势:** 两者合并为同一层，使用与决策有关的价格、成交量、波动率、动量、相对强弱、支撑/阻力等最小信息集解释交易时机与风险。技术信号是概率性上下文，不是确定预测，不堆叠无关指标。
5. **仓位与执行:** 回答“买卖多少、仓位是否合理、执行得怎样”。覆盖仓位和集中度变化、操作序列、手续费来源状态、净结果、执行质量及可核对的反事实比较；不以单次盈亏替代对当时决策过程的评价。
6. **周期深度:** 日报只报告当日新增、状态变化和与操作直接相关的信息；周报完整检查大盘/板块相对表现、个股趋势、仓位变化和一周操作模式；月报刷新投资逻辑、基本面、估值、行业环境、中期趋势和主要风险。不得把同一组套话机械复制到日、周、月。
7. **时间分区:** 动机推断只使用每笔操作发生时点及以前的信息；操作后的价格和结果只能进入事后评价。建议可使用报告 cutoff 及以前的信息。报告必须把“操作前可见上下文”和“操作后检验”分开。
8. **手续费现实:** 正式账本仍只读。已由规则回填的手续费不得继续标为缺失，也不得冒充券商原始实收数据；报告应区分源数据可证明的实际记录、规则回填、正式豁免和未知。若历史现金快照仍携带与当前账本冲突的 `fee_pending` 状态，应在派生报告层重算或明确标为不一致，不得静默沿用。

### Definition of done

- 一个真实交易日的组合日报与无 Decision 标的日报先形成可读样板，并通过用户人工阅读确认；
- P1 标的样板显示股票中文名称（代码），并以四层上下文形成针对该操作和标的的分析，而不是复述固定模板；
- 随后六类报告都可从真实数据生成和浏览，周/月报告是真正的周期汇总而非 episode 列表；
- 无交易日组合日报、无 Decision 动机推断、推荐动作与推荐仓位均有自动化覆盖；
- API、页面、报告存储、补跑和进程内自动生成工作正常且幂等；
- 正式组合数据库前后不变；系统不连接券商、不下单、不保证收益；
- 目标测试、前端测试/构建、真实数据核对和页面验收全部通过；
- 最终停在本地验证候选与本地 Git 提交，不自动推送、合并或部署。

### Truth boundaries

- **工程完成:** 代码、测试、API/UI、自动化和六类报告生成能力通过本合同验证。
- **数据就绪:** 指定真实周期具有足以计算的账本与行情；缺失项诚实显示，不用零或猜测代替。
- **分析证据:** 基本面、估值、大盘、板块、技术与趋势只使用对应判断时点已经存在且可追溯的数据；没有新增证据时报告“无新增可审查变化”，不得用常识、未来信息或搜索结果补造历史事实。
- **动机真值:** `system_inference` 是系统推断，不是用户原始陈述；只使用操作时点之前可用的信息。后续表现只能进入事后复盘。
- **建议真值:** 交易建议使用报告截止时点能够取得的信息，可包含直接动作和仓位，但属于建议而非订单，不承诺结果。
- **人工认可:** P1 样板是否具有实际复盘/决策价值只能由用户确认；执行器不得代替。
- **发布状态:** 工程完成与生产发布分离；本合同不授权 push、PR、merge、deploy、系统服务安装或真实下单。

## Scope and authorization envelope

### In scope

- `src/investment_review/**` 中周期对象、事实聚合、动机推断、推荐生成、存储、runner、render/validation 的必要修改或新增模块；
- `src/portfolio/investment_review_service.py`、`src/portfolio/review_integration.py`、`src/portfolio/web.py` 及直接相关 API 接线；
- `src/portfolio/frontend/src/**` 和对应 `src/portfolio/web_assets/**` 的报告中心界面；
- `tests/test_investment_review_*.py`、`tests/test_portfolio_web.py`、必要 fixtures 与新的周期报告专项测试；
- `reports/investment_review/periodic_v1/**` 的真实样板、核对结果和最终验证摘要；
- 根 `AGENTS.md`、`.agents/skills/investment-review/SKILL.md`、当前实施计划以及本任务包的必要一致性更新；
- 现有 review sidecar 中派生报告状态的幂等写入；正式 portfolio SQLite 只读；
- 固定 conda Python、pytest、现有 Node/Vitest/Vite、SQLite 只读查询、localhost 浏览器/API、现有本地行情缓存和已配置只读行情提供方；
- 本执行分支上的本地 Git checkpoint。

### Out of scope and non-goals

- 新 P2G/P2H 阶段、行为画像、心理/人格诊断、长期干预实验；
- 新的人工审批链、哈希链、回放协议、修订系统、复杂评分或复杂风险模型；
- 决策笔记管理平台、研究工作流扩建、与周期报告无关的重构；
- 修改正式 portfolio SQLite、`data/raw/**`、portfolio accounting 规则或原始成交；
- 券商接入、凭据写入、订单生成/发送、自动交易、保证收益；
- 新外部 provider、无界网络抓取、新运行时依赖或 lockfile 变更；
- push、PR、merge、tag、release、deploy、生产进程修改、OS scheduler/service 安装；
- 批量或递归删除文件/目录。

| Authority area | Allowed | Forbidden or approval required |
|---|---|---|
| Filesystem writes | 上述 source/test/UI/report/package 路径；现有 review sidecar 的派生报告状态 | 正式 portfolio DB、raw、无关用户修改、系统目录 |
| Commands and tests | 固定 conda Python、pytest、npm test/build、SQLite 只读、localhost API/browser、本地 Git | 修改正式 DB、订单/券商命令、破坏性 Git、未知非幂等命令 |
| Network and dependencies | local-first；仅在必要数据缺失时使用现有已配置只读行情 provider，范围限于入选标的和报告周期 | 新凭据、新 provider、新依赖、无界抓取、任何外部写入 |
| External systems | localhost 只读/派生报告服务 | 券商、消息、远端仓库、生产服务写入 |
| Git and publication | 本分支显式路径 stage 和本地 commits | push/PR/merge/tag/release/deploy 均需用户另行明确授权 |
| Destructive actions | 默认无；单个明确且本任务创建的临时文件只有在确有必要时可逐文件处理 | recursive/batch/directory delete；删除用户文件或数据库 |

Routine in-scope local reads/writes, ordinary local commands/tests, package updates, and local Git commits are allowed by default. Omitted consequential authority—destructive actions, external writes, push/merge/publication/deployment, expanded credential use, unbounded dependency/network changes, or material cost—is denied.

### Runtime approval envelope

1. **P1 人工样板门:** P1 完成后，用户必须明确确认 `reports/investment_review/periodic_v1/p1_daily_slice/` 中的组合日报与标的日报可继续扩展。授权 actor=`user`，target=`P1 real daily slice`，grant=`accept_p1_sample_and_continue`。未获得时将任务标记 `blocked`，不得进入 P2。
2. **发布门:** push、PR、merge、deploy 或生产运行必须由用户另行授权并在本合同/START 中记录精确目标。
3. **系统调度门:** 可以实现并测试进程内/CLI 自动生成；安装 Windows 计划任务、服务或开机启动必须另行授权。

User authorization recorded in `START_HERE.md` may activate or revise this envelope. Consequential external, destructive, publication, deployment, credential, or high-cost actions require explicit authority.

## Decision register

| Decision ID | Class (`fixed`, `delegated`, `blocking`) | Decision or bounded choice | Evidence or authority |
|---|---|---|---|
| D-001 | fixed | 六类周期报告、无 Decision 动机推断、直接交易建议和仓位建议均属于 V1 | 用户目标 + 实施计划 |
| D-002 | fixed | 正式 portfolio SQLite 只读；不接券商、不下单、不保证收益 | AGENTS.md + investment-review skill |
| D-003 | fixed | 不新增 P2G/P2H、画像、复杂模型或重型审计；旧 P2 工件只按需复用 | 用户目标 + 实施计划 |
| D-004 | delegated | 选择最近一个数据足够且包含无 Decision 操作的真实日期和标的作为 P1 样本，并记录选择依据 | 必须从真实只读数据证明 |
| D-005 | delegated | 在现有代码结构内选择最小周期报告 schema、模块拆分、存储/API 路径和推荐算法 | 不得扩大 V1 或新增依赖 |
| D-006 | delegated | 数据不足时降低推断/建议可信度或拒绝精确仓位，但仍输出可解释的最低可用建议 | 不得伪造数据或保证结果 |
| D-007 | blocking | P1 样板必须由用户确认后才能进入 P2–P4 | 用户在实施计划中的固定门 |
| D-008 | blocking | 若完成必须写正式 DB、接券商、增加凭据/依赖、改变 accounting 或覆盖不明用户修改，停止并询问 | 需要新授权或设计决定 |
| D-009 | fixed | 周期复盘采用“基本面与估值—大盘与板块—技术与趋势—仓位与执行”四层框架，并按日/周/月逐级加深 | 用户 2026-07-28 明确确认 |
| D-010 | fixed | 首版 P1 样本未获接受，必须修复中文名称、机械分析和手续费误报后重新通过 P1 工程验证与人工门 | 用户 P1 样本反馈 |
| D-011 | fixed | 用户已在正式库完成手续费规则回填；当前库只作为新的只读事实基线，回填费用需保留来源性质 | 用户说明 + `portfolio_fee_backfill_20260728T062640Z.json` |

## Deliverables

| Deliverable ID | Exact path or external target | Required content | Completion evidence |
|---|---|---|---|
| O-001 | `src/investment_review/**` | 周期报告对象/生成、动机推断、推荐生成、存储与 runner 接线 | V-101/V-201/V-301 |
| O-002 | `src/portfolio/investment_review_service.py`, `src/portfolio/review_integration.py`, `src/portfolio/web.py` | 六类报告 API、查询、补跑、健康与自动生成接线 | V-301/V-401 |
| O-003 | `src/portfolio/frontend/src/**`, `src/portfolio/web_assets/**` | 最新报告首页、组合/标的与日/周/月切换、建议/风险/依据展示 | V-102/V-402 |
| O-004 | `tests/test_investment_review_periodic_reports.py`, `tests/test_investment_review_motive_inference.py`, `tests/test_investment_review_recommendations.py` 及直接相关既有 tests | 正反例、时间边界、缺失 Decision、建议、幂等、API/UI/自动化覆盖 | V-101–V-999 |
| O-005 | `reports/investment_review/periodic_v1/p1_daily_slice/` | 真实组合日报、真实无 Decision 标的日报、四层上下文、中文名称、手续费来源与现金一致性核对、限制 | P1 人工门 |
| O-006 | `reports/investment_review/periodic_v1/final/` | 六类真实样本矩阵、验证摘要、已知限制、source DB 只读确认 | V-999 |
| O-007 | `docs/codex_tasks/investment_review_periodic_v1/{CONTRACT.md,START_HERE.md}` | 活合同、断点、授权与完成证据 | package validator |

## Execution phases

### P1 — 真实日报垂直样板

- **Outcome:** 一个真实交易日的组合日报与一个无 Decision 标的日报可以通过 API/UI 直接阅读；两份报告显示中文名称（代码），包含表现、持仓/风险变化、四层决策上下文、非机械的动机推断、操作前/后分区、操作评价、直接交易建议、建议仓位、风险和失效条件，并正确反映当前手续费来源状态。
- **Deliverables:** O-001/O-003/O-004 的最小日报实现；O-005 全部文件；P1 checkpoint。
- **Validation and evidence:** V-101、V-102、V-201；正式数据库前后只读校验；动机输入时间不晚于操作；建议输入时间不晚于报告 cutoff；用户人工阅读确认。
- **Important boundaries or recovery notes:** 优先复用现有 runner、事实包、行情、API/UI，不先泛化六类报告。P1 工程验证通过后必须停止并请求 `accept_p1_sample_and_continue`；用户提出修改时修订同一合同并迭代 P1。

### P2 — 日报全面生成

- **Outcome:** 每个交易日都有组合日报；当日持有或交易过的标的都有标的日报；无交易日组合报告仍包含表现、风险与建议；重复运行幂等。
- **Deliverables:** 日报通用 period/subject 选择、存储/API/UI 历史导航、连续真实日期证据。
- **Validation and evidence:** V-301；至少连续三个真实交易日，覆盖有交易、无交易、无 Decision、开放持仓和已退出标的。
- **Important boundaries or recovery notes:** 不为普通报告增加新审批/回放层；若历史数据不足，诚实限制回填范围但保持生成器可用。

### P3 — 自然周与自然月报告

- **Outcome:** 组合与单标的周报/月报是自然交易周/月的独立周期汇总，包含归因、仓位变化、操作序列、主要动机和下一周期建议，不再是逐 episode 报告列表。
- **Deliverables:** 四类周/月报告、周期边界和聚合实现、真实样本矩阵。
- **Validation and evidence:** V-401；周期汇总与底层日级事实对账；周/月边界、跨月周、无交易周期和重复运行正反例通过。
- **Important boundaries or recovery notes:** 复用同一报告 contract，不复制六套生成逻辑；事后结果与操作时动机严格分区。

### P4 — 报告中心、自动生成与候选闭合

- **Outcome:** 页面默认展示最新报告，可切换组合/标的、日/周/月和历史日期；进程内/CLI 收盘后、周末、月末生成与补跑工作正常；六类真实样本和最终验证闭合。
- **Deliverables:** O-002/O-003/O-006；更新后的 START；本地最终 checkpoint。
- **Validation and evidence:** V-402、V-501、V-999；API/browser 阅读验证；自动生成失败可见且可补跑；正式数据库不变。
- **Important boundaries or recovery notes:** 只实现和测试现有进程内/CLI 自动化；不得安装 OS scheduler/service，不得推送、合并、部署或执行报告建议。

## Completion criteria

| Criterion ID | Exact requirement | Required evidence | Validator or review method | Blocking class |
|---|---|---|---|---|
| C-ENG-001 | 组合/标的 × 日/周/月六类报告均可生成、存储、查询和阅读 | 六类真实样本矩阵 | V-401/V-402/V-999 | engineering |
| C-ENG-002 | 周/月报告是周期对象，不是 episode 列表或重复的单笔报告 | schema、API payload、真实报告 | 专项 tests + 人工结构检查 | engineering |
| C-ENG-003 | 无 Decision 不阻塞，输出 `system_inference`、依据、替代解释、定性可信度和缺失信息 | P1 报告 + tests | V-101/V-201 | engineering |
| C-ENG-004 | 每份报告给出动作建议与建议仓位/区间，并包含期限、依据、风险、失效条件和数据时间 | 六类样本 + tests | V-101/V-401 | engineering |
| C-ENG-005 | 无交易日组合日报和数据不足降级均可用且不伪造数据 | fixtures + 真实样本 | V-301 | engineering |
| C-ENG-006 | 报告中心默认最新并支持 subject/period/date 导航 | API/browser evidence | V-402 | engineering |
| C-ENG-007 | 日/周/月自动生成和补跑幂等，失败状态可见 | automation receipts/tests | V-501 | engineering |
| C-ENG-008 | 标的报告、操作条目和建议区域显示股票中文名称（代码）；已知名称不得丢失 | P1 报告/API/UI + tests | V-101/V-102/V-201 | engineering |
| C-ENG-009 | 报告采用四层框架，日报只呈现新增或操作相关信息，周/月逐级加深；不得机械复制同一分析 | P1 样本 + 六类样本矩阵 | 专项 tests + 人工结构检查 | engineering |
| C-ENG-010 | 技术与趋势合并为概率性交易上下文；大盘/板块共同涨跌不得直接冒充用户动机 | P1 报告 + 正反例 tests | V-101/V-201 | engineering |
| C-DATA-001 | 正式 portfolio SQLite 始终只读且前后内容不变 | before/after 文件信息与 SHA-256 | V-201/V-999 | data_readiness |
| C-DATA-002 | 已回填手续费不再报缺失，且实际记录、规则回填、正式豁免、未知不会互相冒充；现金口径冲突可见 | P1 数字核对 + tests | V-101/V-201 | data_readiness |
| C-TIME-001 | 动机只使用操作时点可用信息；建议只使用报告 cutoff 可用信息；事后结果分区 | positive/negative tests | V-101/V-401 | engineering |
| C-SAFE-001 | 不保证收益、不自动下单、不使用券商凭据 | source scan + tests + UI check | V-999 | engineering |
| C-HUMAN-001 | 用户明确接受 P1 真实样板后才进入 P2 | START authorization record | 用户明确答复 | human_approval |
| C-REL-001 | 形成验证通过的本地候选与本地 commits，未 push/merge/deploy | Git log/status + final readout | V-999 | release_readiness |

All required criteria must pass. The executor cannot waive, weaken, or replace a criterion.

## Validation matrix

固定 Python：`C:\Projects\03_Investment_System\.conda\investment-system\python.exe`。

| Validation ID | When | Exact command or method | Expected result | Evidence path |
|---|---|---|---|---|
| V-001 | setup/resume | `python -X utf8 C:\Users\Q\.codex\skills\autonomous-stage-runner\scripts\task_package.py validate docs/codex_tasks/investment_review_periodic_v1 --require-ready` | package valid | START checkpoint |
| V-101 | P1及final | `python -m pytest -q -p no:cacheprovider tests/test_investment_review_periodic_reports.py tests/test_investment_review_motive_inference.py tests/test_investment_review_recommendations.py tests/test_investment_review_review_runner.py tests/test_investment_review_product_api.py tests/test_investment_review_p2f_e2e.py` | no failure/error | START validation summary |
| V-102 | P1及final | 在 `src/portfolio/frontend` 运行 `npm test -- --run` 与 `npm run build` | tests/build pass，web_assets 更新一致 | START validation summary |
| V-201 | P1 | 从正式 DB 只读选择样本，生成 O-005；核对组合/标的数字、四层上下文、中文名称、手续费来源、现金一致性、时间边界和 DB before/after SHA-256 | 两份报告可读且非机械，当前基线 `6207d15cc61cffd963cc8154a1b9af2ddae56ae11efe9a26116f7792e6ffb057` 在本轮前后不变 | `reports/investment_review/periodic_v1/p1_daily_slice/` |
| V-301 | P2 | 运行连续三日专项 tests 与真实生成/重复生成 | 有交易/无交易/无 Decision/开放/退出覆盖；repeat idempotent | START checkpoint |
| V-401 | P3 | 运行周/月专项 tests，生成真实 portfolio/instrument weekly/monthly 并与日级事实核对 | 四类报告正确、自然周期边界正确 | final sample matrix |
| V-402 | P4 | localhost API/browser 检查最新页、导航、六类报告、建议/风险/依据/缺失状态 | reader-facing flow pass | `reports/investment_review/periodic_v1/final/` |
| V-501 | P4 | `python -m pytest -q -p no:cacheprovider tests/test_investment_review_product_automation.py tests/test_investment_review_product_api.py tests/test_portfolio_web.py` | automation/API/web pass | final validation summary |
| V-999 | final | rerun V-101/V-102/V-501；`git diff --check`；检查 source DB SHA、scope、Git log/status、未发布状态 | all required criteria pass，只有授权路径，local candidate ready | O-006 + final START |

## Checkpoint and resume protocol

1. 保留基础提交 `7df75562eb7c7123ff066406f92fd6b844be994b`；它只包含本任务相关规则、活动边界、页面提示、P2F 建议许可和对应测试，没有吸收 P2G/P2H 或其他工作树修改。
2. 任务包 checkpoint 只提交本目录下的 `CONTRACT.md` 与 `START_HERE.md`。
3. P1 先选择真实日期/标的并记录依据，再实现最小垂直链路；不要先泛化所有周期。
4. P1 工程验证通过后更新 START、创建本地 checkpoint，并将 state 设为 `blocked`，向用户展示两份报告并请求 `accept_p1_sample_and_continue`。
5. 用户接受后，把授权原文和时间记录到 START，将 state 恢复 `running`，依次执行 P2、P3、P4。
6. 每个有意义里程碑更新 START 的完成工作、下一阶段、验证、限制和一个下一安全动作；相邻阶段可合并一个 commit。
7. resume 时从最早未证明 outcome 开始；普通 branch drift、hash warning 或可解决冲突不是新建任务包的理由。
8. 最终只有全部 criterion 通过才能设 `complete`；否则保留 `running` 或真实 `blocked`。

At meaningful milestones: update `START_HERE.md`, run proportionate validation, and create a Git checkpoint when useful. Multiple adjacent phases may share one checkpoint. On resume, start from the earliest useful outcome not yet proven.

## Stop conditions

- 需要写正式 portfolio DB、改变 accounting/raw facts、连接券商或执行订单；
- 需要新增 provider、凭据、运行时依赖、lockfile、无界网络或明显成本；
- P1 样板未获用户接受却准备进入 P2；
- 真实数据不足以产生任何可核对 P1 样板，且现有只读 provider 不能在授权范围内补足；
- 修改会覆盖意图不明的用户工作，或需要批量/递归删除；
- 必须 push、merge、deploy、安装系统任务/服务而未获授权；
- 完成需要伪造动机、行情、仓位、推荐依据、用户认可或测试结果。

Stop only for conflicting authoritative instructions, user changes that would be overwritten with unclear intent, consequential actions without authority, unavailable essentials with no independent work remaining, harmful uncertain non-idempotent state, or completion that would require fabricated facts. Hash drift, branch advancement, dirty files, ordinary conflicts, and validator warnings are not hard stops.

## Publication and final handoff

仅授权 `codex/investment-review-periodic-v1` 上的本地 commits。禁止 push、PR、merge、tag、release、deploy、生产服务修改、OS scheduler/service 安装和订单执行。

最终交付必须列出：工作树与分支、source baseline、setup/阶段 commits、修改路径、六类真实样本位置、P1 用户接受记录、全部 validators、正式 DB before/after、已知数据限制、自动化状态，以及 `orders_executed=false`、`guaranteed_return_claims=false`、`production_released=false`。

The normal unattended endpoint is a verified candidate artifact or branch for human review, not an automatic merge or deployment unless explicitly authorized above.
