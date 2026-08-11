# 系统规则递归、规模膨胀与判断机械化：整合只读诊断

## 1. 记录信息

| 字段 | 内容 |
|---|---|
| date | `2026-08-10`（Asia/Shanghai） |
| scope | A-share Research OS 主线、Portfolio Tracker、Investment Review 相关活动分支与历史治理资产 |
| status | `read_only_diagnostic` |
| baseline | `origin/main@d21aa5a9fc4e0a8aaf77ad4d6c7ba3dd814b79d8` |
| changed_paths | 本诊断、`docs/plans/p1_6_system_complexity_remediation_plan.md`、`docs/index.md` |
| verification | 对远端主线快照、canonical run、活动规则文件、历史治理合同、相关工作树代码和 Git 文件清单做只读复核；未运行投资研究、未改正式数据库 |
| open_risks | 分支间产品边界尚未统一；Portfolio/Investment Review 仍是分支产品；数量统计只代表本快照 |

## 2. 文档边界

这是一份时间点诊断和工程决策输入，不是新的 policy、workflow 事实源、checklist、Gate、评分表或完成状态。它不自动授权删除、迁移、发布或改写历史，也不要求其他模块长期“执行本诊断”。

本诊断对应的有限实施路线见[系统复杂度修正计划](../plans/p1_6_system_complexity_remediation_plan.md)。计划允许后续实质修改 `AGENTS.md`、工作流内核、policy、skills、schema、实现和测试；这里没有把它们排除在重构范围之外。边界只是：不能把“反递归”本身再写成一套新的常设治理体系。

## 3. 总结结论

你描述的规则递归在当前项目中不是抽象风险，而是已经发生过的工程历史；但它没有均匀污染整个系统。

> 事实与会计层总体健康，研究证据层的大部分复杂度确实保护了投资真实性；元治理、历史兼容、发布证明和任务授权层曾明显递归膨胀；Scorecard、遗留 Reader rubric 与 Investment Review 的固定仓位动作则已在局部把判断压缩成规则匹配。当前远端主线已经主动收缩默认路由，因此系统尚未全面退化成规则引擎，但仓库和认知表面仍背负很重的控制外壳。

真正需要修正的不是“规则数量太多”这一抽象指标，而是四类具体错位：

1. 活动代码在缺少用户风险预算时仍能生成确定动作和仓位区间；
2. 缺失或低置信度证据仍可能被表达为数字分数、综合优先级或类似 Kill Switch 的确定条件；
3. 同一完成语义、质量语义和产品边界在多个文档与分支中重复定义；
4. 历史 R5/Bundle/Patch 的证明资产虽然退出默认权力链，仍占据大量文件、测试、搜索结果和维护注意力。

## 4. 检查范围与证据边界

### 4.1 主线基线

本诊断使用干净 linked worktree 检查 `origin/main@d21aa5a`。该提交是 2026-07-28 合并的 V1 治理集成结果。仓库内的 v12 clean-checkout 记录显示全量测试为 `979 passed, 2 skipped`，见[`START_HERE.md`](../codex_tasks/v1_governance_integration_cleanup_v12/START_HERE.md)。

当前机器索引把 002837 的 current run 指向：

```text
wf_20260725_stock_first_002837_v1_policy_refresh
status: accepted_with_todos
```

证据见[`config/r5_readout_canonical_index.yaml`](../../config/r5_readout_canonical_index.yaml)。该 run 的 G0–G10 全部通过，G5 为 `not_applicable`；4 条 high issue 均显式保留为未使用、非阻断的 unknown 或 method limitation，见[`quality_gate_report.md`](../../reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh/quality_gate_report.md)与[`open_todos.csv`](../../reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh/open_todos.csv)。

这里必须区分两类事实：V1 工程候选已经合并并通过 clean-checkout 验证；但这个 002837 run 自身仍记录 `system_v1_complete=false`、`sample_quality_ready=false`、`p2_ready=false` 和 `release_ready=false`。前者是项目集成事实，后者是 run-local 字段。它们不应互相代替；当前并存也说明项目级与运行级状态的职责还没有完全收束。

### 4.2 相关分支

Portfolio 与 Investment Review 尚未形成一个统一的主线产品。本次只读检查覆盖了以下快照：

| 分支快照 | 检查时 HEAD | 与后续分支的关系 | 观察 |
|---|---|---|---|
| `codex/investment-review-product-completion` | `c3e2966` | `reviewability`、`periodic-v1` 和 `portfolio-tracker` 的祖先 | facts-only/no-advice 的 product-completion 基线，只作为回归参照 |
| `codex/investment-review-reviewability-corrections` | `c2db0d9` | 比 completion 多 21 commits，且是 periodic-v1 的祖先 | committed 增量引入 reviewability、checkpoint、时间证据与多代合同，是元控制膨胀的重要工程样本 |
| `codex/investment-review-periodic-v1` | `aac8290` | 比 reviewability 多 18 commits；是 portfolio-tracker 的直接祖先 | P8–P10 周期报告与风险回测检查点；`C-HUMAN-005` 仍待用户决定 |
| `codex/portfolio-tracker` | `f56854b` | 比 periodic-v1 多 1 commit，是当前产品线最新 committed tip | Portfolio 会计、本机应用、周期 Review 与盘中价/费用能力汇合于此，作为 Review 修正的 committed 基线 |

所以，前三个路径不是三个平行产品，而是同一提交链上的历史/阶段 worktree：

```text
c3e2966 product-completion
  → +21 commits c2db0d9 reviewability
  → +18 commits aac8290 periodic-v1
  → +1 commit  f56854b portfolio-tracker
```

这消除了“需要合并三次”的误解，但没有消除语义冲突：Review advice 边界在不同检查点中改变。`origin/main` 与 `portfolio-tracker` 又从旧共同祖先分叉，双方相对各有 117/93 个独有 commits；因此不能把任一 Review/Portfolio 分支整树合入 Research main。

后续应从 `f56854b` 的精确 committed tip 新建隔离集成分支，把 completion 当作安全行为基线、periodic-v1 当作 P8–P10 证据来源，并只定向移植经审查的实现。

这里还提供了新的递归证据：reviewability 的业务目标是让操作复盘“可审阅”，但其 committed 增量又形成 v3–v7 多代合同、checkpoint schema、知识时间、provider allowlist、缓存回执和验收包。部分严格性保护了时间真值与正式账本，另一部分已经明显转化为元控制表面。因此不能把规则压缩本身视为重构完成，仍需同时核对产品边界与完整周期报告行为。

### 4.3 事实、推断与建议

- 文件数量、路径、字段、代码阈值、状态和测试记录属于可复核事实。
- “复杂度主要服务投资还是服务系统自身”属于基于这些事实的架构判断。
- 删除、合并、改写、退役顺序属于后续计划，不是本诊断自动推出的事实。

## 5. 当前系统分层与阶段

| 层/产品 | 核心职责 | 当前阶段 | 诊断 |
|---|---|---|---|
| Research evidence | 原始证据、Evidence、Claim、Metric、Exposure、报告派生 | V1 工程主线已集成；002837 current run 为 `accepted_with_todos`；样例质量和 P2 未放行 | 严格性大多服务真实性，应保留 |
| Research orchestration | 五类 workflow、T0–T10、G0–G10、状态与 readout | 默认路由已收缩，legacy evaluator 已退出普通路径 | 方向正确，但状态和控制产物仍偏重 |
| Portfolio Tracker | 交易流水、现金、成本、持仓、行情、历史快照 | 分支产品可用且继续演进；不是远端主线的一部分，也不是在线部署服务 | 会计机械化合理，不能因“简化”而削弱 |
| Investment Review | 复盘事实、行为解释、组合风险、周期报告与建议 | 多个候选分支并存；P10 参数仍需用户决定；未形成统一稳定产品 | 最需要保留判断，也最容易被固定阈值机械化 |
| Legacy/governance | Bundle、Patch、contract、validator、receipt、兼容和发布证明 | 已退出普通 canonical 权力链，但仍大量存在于仓库 | 当前主要认知负担和历史工程外壳 |
| Deployment | 源码托管、CI、运行方式 | 有 GitHub 仓库与 CI；没有正式 release/tag、Docker、托管站点或在线自动交易部署 | 不能把“代码存在”描述成“系统已上线” |

研究内容规模仍很有限：`reports/segments/**` 与 `reports/stocks/**` 共 27 个 tracked 文件，而 `reports/workflow_runs/**` 有 125 个、`reports/p1_6/**` 有 199 个。这意味着当前更接近“研究操作系统工程已搭起、研究覆盖尚少”，而不是已经形成广覆盖的成熟研究库。

## 6. 哪些复杂度服务投资，哪些服务系统自身

### 6.1 应保留的投资真实性约束

以下机制约束的是材料真实性、时点和可复现性，而不是替 Agent 作投资判断：

- `data/raw/` 不覆盖，原始材料与加工结果分离；
- 官方披露、结构化数据、市场上下文与新闻线索分层；
- `fact / estimate / inference / management_comment / analyst_view / opinion / unknown` 分离；
- Metric 保存期间、单位、来源和计算方法；
- 冲突证据、风险、反证和缺失项可见；
- Segment 与 Company 通过多对多 Exposure 表达；
- 新证据改变旧结论时留下 change log；
- Portfolio 使用追加式账本、去重、事务和可重放会计；
- Review 使用当时可得信息，避免用未来结果重写过去动机。

这些约束允许系统诚实地从“有证据的事实”走向“有边界的推断”，也允许停在 `unknown` 或省略结论。它们承认 specification gap，而不是消灭它。

### 6.2 工程可靠性约束

Schema、类型校验、幂等性、数据库备份、哈希、路径存在性、引用完整性和 CI 都有合理用途。问题不在于这些能力存在，而在于它们是否被无差别应用到每一个中间步骤，以及是否开始替代“研究是否真正有洞察”的判断。

### 6.3 主要服务系统自身的复杂度

下列链条的主要对象已经不是公司、行业或组合，而是证明系统自己的权限、版本和完成状态：

```text
pack
→ contract
→ validator
→ gate
→ readout
→ receipt
→ compatibility
→ governance cleanup
→ amended contract
```

这些资产有历史审计价值，但不应继续成为普通研究的默认前置条件。

## 7. 规则递归已经发生的直接证据

### 7.1 治理清理本身发展成 12 个版本

[`v1_governance_integration_cleanup_v12/CONTRACT.md`](../codex_tasks/v1_governance_integration_cleanup_v12/CONTRACT.md)明确记录：未披露的细粒度经营数据、Bundle11R–16R 字段完整性和中间人工审核，曾被活动质量规则机械提升为全局 blocker。系统因此可以诚实表达“不知道”，却仍被自己的流程长期判为未完成。

从基础版到 v12，共有：

- 12 个合同版本；
- 24 份 `CONTRACT.md` / `START_HERE.md`；
- 15,303 行文本。

目的本来是收缩治理，但修正过程又产生了新的授权边界、波次、收据、恢复证明和合同修订。这不是单条规则设计错误，而是“用更高一层规则处理规则冲突”的真实递归。

### 7.2 权限合同形成工程死锁

[`p5_authority_conflict.yaml`](../../reports/p1_6/r5_v1_governance_cleanup/validation/p5_authority_conflict.yaml)记录了一个典型闭环：

1. 活动代码、测试和 CI 必须停止读取 Night、Bundle 与旧 002837；
2. 真正需要修改的脚本和测试不在 P5 获准修改集合中；
3. 保留物理依赖会违反清理目标；
4. 跳过或弱化测试又违反验证合同；
5. 只能再创建 amended contract 扩大权限。

每条局部约束都可解释，组合后却使“修复规则”必须先“修复修复权限”。这是本项目最直接的元控制递归证据。

## 8. 规模膨胀的实际位置

以下统计均来自 `origin/main@d21aa5a` 的 tracked 文件：

| 指标 | 数量 |
|---|---:|
| tracked 文件 | 1,922 |
| 路径名含 R5 | 824 |
| 路径名含 Bundle | 378 |
| 路径名含 Patch | 177 |
| `scripts/*.py` | 88 |
| 其中路径名含 R5/Bundle/Patch | 76 |
| `tests/test_*.py` | 184 |
| 其中路径名含 R5/Bundle/Patch | 134 |
| `codex_tasks/**` 与 `docs/codex_tasks/**` | 245 |
| `reports/segments/**` 与 `reports/stocks/**` | 27 |
| `reports/workflow_runs/**` | 125 |
| `reports/p1_6/**` | 199 |

当前 002837 policy-refresh 自身有 17 项 manifest 工件。六个控制面文件合计约 22.4 KB，七个 `research/` 文件合计约 25.0 KB，`workflow_state.yaml` 有 320 行。单个治理刷新 run 中，控制面已与研究内容处于同一数量级。

这些数量不能证明每个历史文件都应删除；它们证明开发注意力和可搜索表面已经明显偏向系统自证，而不是新增研究对象与投资命题。

## 9. 当前主线已经做出的有效收缩

现行主线不是继续无条件堆叠规则，它已经完成几项关键收缩：

- 永久 workflow 限制为五类；
- canonical Gate 限制为 G0–G10；
- Bundle11R–16R 和 legacy R5 local checks 退出普通 orchestrator 默认路由；
- legacy evaluator 只能显式检查局部 capability，不能直接改写 canonical outcome；
- `severity=high` 不再自动等于 `blocks_current_goal=true`；
- 中间 Evidence、Claim、Metric 和 hash 由机器检查，活动人审收束到最终报告；
- 可见、未使用的 unknown/limitation 可以留在 `accepted_with_todos`。

这些边界见[`RESEARCH_WORKFLOW.md`](../workflows/RESEARCH_WORKFLOW.md)第 11、13、14 节。当前 002837 run 的 4 条 high issue 均保持 open，但不会因缺失未使用数据而阻断窄目标，说明这次收缩已经产生实际效果。

需要警惕的是：判断并未消失，而是移动到了 `impact_scope`、`active_disposition`、`affected_capabilities` 和 `blocks_current_goal`。如果未来继续为这些字段叠加更细阈值、例外和审批，它们也会重新形成元规则递归。

## 10. 判断被机械化的具体位置

### 10.1 Scorecard 的伪精确

当前[`002837 stock_scorecard.yaml`](../../reports/stocks/002837_invic/stock_scorecard.yaml)中，`revenue_visibility`、`customer_quality`、`governance_quality` 和 `valuation_scenario_risk` 的证据包含 `TODO`，但仍分别得到 1 或 2 分，最终又生成 `final_priority: deep_watch`。

这些分数可以是分析者判断，但文件没有把“证据支持的事实评分”与“低置信度主观占位”充分分开。数字因此产生了超出证据的精确感。类似“连续两期无披露”的条件也更接近刷新触发器；仅仅没有披露，不等于业务不存在或投资命题已被反证。

### 10.2 遗留 Reader rubric 鼓励为系统写作

[`config/r5_reader_quality_rubric.yaml`](../../config/r5_reader_quality_rubric.yaml)包含：

- 82 分 candidate 阈值和 45 分 research-draft 阈值；
- 3,200 个汉字的总长度下限；
- 每节固定字数和引用数量；
- judgment、causal、counterevidence、watchpoint 等信号及比例。

它能发现空报告和明显缺项，却无法证明报告真正有洞察。固定长度、引用配额和关键词比例很容易诱导扩写、堆引用和信号填充，形成“为了过 rubric 而研究”。好消息是它已退出默认路由；风险在于它仍以完整活动配置和大量测试形式占据认知表面，未来可能被误恢复为默认质量标准。

### 10.3 Investment Review 在缺少用户风险预算时仍输出动作

在 `codex/portfolio-tracker@f56854b` 与 `codex/investment-review-periodic-v1@aac8290` 的 `src/investment_review/periodic_reports.py` 中，代码同时写入：

```text
MISSING_EXPLICIT_USER_RISK_BUDGET
```

却仍把以下条件直接映射为动作：

```text
top_weight > 20% or cash_weight < 5%
→ reduce
```

单标的分支还会输出 `hold/reduce` 和 5%–10%、8%–12%、12%–18% 等目标区间。基本面、市场、板块和技术上下文主要改变解释、风险和 confidence，没有真正决定动作。

与此同时，`codex/investment-review-periodic-v1@aac8290` 的 `reports/investment_review/periodic_v1/strategy_drawdown_validation/P10_READOUT.md` 已经明确：真实样本不支持把 20% 作为单变量机械减仓开关，最终风险架构 `C-HUMAN-005` 仍需用户决定。该证据属于独立分支快照，不伪装成 `origin/main` 内文件。

因此当前存在明确矛盾：分析文本承认需要联合判断，建议生成器仍在风险预算缺失时使用内置阈值产生确定动作。这是优先级最高的活动代码风险。它尚未连接券商或自动执行，也未作为在线服务部署，但未来报告可以真实触发这种机械输出。

### 10.4 产品边界在分支间分裂

`origin/main` 与 `codex/investment-review-product-completion` 均保留 no-advice；`codex/portfolio-tracker` 和 `codex/investment-review-periodic-v1` 把 Investment Review 定义为可输出个性化 `buy/sell/hold` 与仓位建议的例外；`codex/investment-review-reviewability-corrections` 又把直接建议写入根 `AGENTS.md` 和 skill。

这不是简单的“哪条规则优先”问题，而是 Research、Portfolio 和 Review 三个产品尚未有稳定职责边界。如果继续用例外条款覆盖全局 no-advice，再用更多测试解释例外，就会再次进入规则—例外—例外约束的递归。

### 10.5 当前状态入口漂移

README 仍让读者通过[`R5_READOUT_CANONICAL_INDEX.md`](../../reports/p1_6/R5_READOUT_CANONICAL_INDEX.md)理解具体 R5 Bundle 与 gate 状态。这个 Markdown 索引保留大量 `canonical` Patch/Bundle 项，并仍把旧 Bundle13R close readout 标为 canonical。

机器 YAML 的 `current_runs` 则唯一指向 2026-07-25 的 policy-refresh run。两者并非两个同等有效的运行时事实源，但 README 的导航容易使人这样理解。

这是典型的治理副作用：为了消除状态歧义建立 canonical index，最终又形成机器 current pointer 与历史 canonical readout 目录的职责漂移。

### 10.6 自动通过的证明边界容易被误读

当前 002837 run 可以得到：

```text
G0–G10 pass
automated_report_quality = pass
status = accepted_with_todos
```

它能够证明引用、来源、缺口可见性、类型、工件结构和窄任务的诚实关闭；它不能证明竞争优势成立、Exposure 分数唯一正确、估值合理、投资命题成立或样本有足够洞察。

当前系统已经把自动通过、最终报告人审、样例质量和 P2 readiness 分开，方向正确。风险来自使用者看到 `pass`、`accepted`、`deep_watch` 或数字分数后，赋予它们合同并未证明的确定性。

## 11. 核心文档与活动语义的重复

当前核心文件规模如下：

| 文件 | 行数 | 主要问题 |
|---|---:|---|
| `AGENTS.md` | 123 | 适合作共享边界，但分支间产品定义已漂移 |
| `docs/workflows/RESEARCH_WORKFLOW.md` | 608 | 同时承担 kernel、字段语义、legacy 边界和阶段条件 |
| `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | 325 | 与 workflow 重复部分完成与质量语义 |
| `docs/policies/EVIDENCE_AND_CITATION_POLICY.md` | 248 | 证据规则总体合理 |
| `docs/policies/QUALITY_GUARDRAILS.md` | 326 | 同时包含质量规则、workflow 状态语义和产品例外 |
| `research-orchestrator/SKILL.md` | 295 | 重复全局完成和 issue 语义 |
| `quality-review/SKILL.md` | 430 | 大量 legacy/R5 兼容与全局状态语义 |
| `stock-deep-dive/SKILL.md` | 449 | 同时承载业务执行、R5 兼容、样例质量和完成语义 |

问题不是单纯“行数过多”，而是同一个概念在 workflow、spec、policy 和多个 skill 中同时展开。一旦一个定义改变，就需要多处同步；为了防止不同步又会增加 validator 和契约。这正是后续应当直接修改核心文件的原因。

## 12. 根因判断

综合两个检查结果，当前复杂度由以下机制共同形成：

1. **补丁式演化。** 每次局部缺陷都新增 Patch/Bundle/validator，而不是回到唯一 owner 修正已有语义。
2. **把工程完成、研究完成、样例质量、P2 与发布证明叠在同一控制面。** 多个完成概念需要互相解释，形成额外状态和 truth table。
3. **权限清单替代了普通变更审查。** 精确 allowlist 在高风险删除时合理，但扩展到普通修复后形成“必须改却无权改”的死锁。
4. **历史资产仍以活动命名和活动配置存在。** 即使默认路由已退役，文件名、测试和索引仍让它们看起来像当前系统。
5. **用可量化代理替代不可完全量化的质量。** 字数、引用数、关键词比例、分数和固定仓位阈值被用于获得一致性，却产生伪精确和可被迎合的目标。
6. **产品边界未先稳定。** Research 的 no-advice、Portfolio 的会计职责与 Review 的个性化决策支持在不同分支以全局规则和例外互相覆盖。

## 13. 最终判断与修正优先级

本系统不应被概括为“规则已经全面失控”，也不应被概括为“只需增加更多规则”。更准确的判断是：

1. 事实、证据与会计层的机械化基本健康；
2. 研究证据复杂度大多服务投资真实性；
3. R5/Bundle/任务合同/发布证明已经发生过真实元控制递归；
4. 当前主线已经切断 legacy 的默认控制权，但物理与认知外壳仍很重；
5. 固定仓位动作、TODO 数字评分、披露缺失型 Kill Switch、Reader rubric 和状态入口漂移，是当前需要直接修正的具体位置；
6. `AGENTS.md`、工作流内核、policy 和 skills 必须进入后续重构范围，否则只改导航和历史文件确实会流于表面。

修正顺序应是：先停止活动路径中的错误确定性，再统一产品边界和当前事实入口，随后收缩核心文档职责与默认运行路径，最后才处理历史资产。完整步骤、修改对象、保留能力、验证方式和暂停点见[修正计划](../plans/p1_6_system_complexity_remediation_plan.md)。

## 14. 本次文档变更验证

- 新增两份文档中的相对 Markdown 链接逐项解析：`0` 个断链；
- `scripts/check_doc_drift.py`：`pass`；
- `pytest tests/test_p0_acceptance.py -q`：`1 passed`；
- `git diff --check`：`pass`；
- 新文件尾随空白检查：`0`；
- 未运行研究 workflow、未访问外部行情、未修改 Portfolio 正式 SQLite、未修改任何活动规则或代码行为。

本诊断到此结束。它提供观察与实施依据，但不继续生长为一套需要长期维护的“反递归规则”。
