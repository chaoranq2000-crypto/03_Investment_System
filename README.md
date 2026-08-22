# A-share Research OS / A股投研工作区

> 这是一个证据驱动的 A 股投研工作区。Research 不输出直接交易建议，Portfolio
> 只维护账务事实；独立 Investment Review 只有在显式当前输入齐备时才可给出建议。
> 三个产品都不连接券商、不执行订单、不保证收益。

## 项目定位

A-share Research OS 的目标是把 A 股投研过程拆成可维护、可复用、可审查的工作流：

```text
用户输入：细分方向 / 股票 / 对比任务 / 更新任务
        ↓
Codex Skills：标准化投研动作
        ↓
研究对象库 + 证据库：沉淀证据、事实、指标、映射关系和状态
        ↓
产出层：细分报告、个股深度、对比矩阵、观察清单、投资备忘录
```

核心原则：

- 证据库是核心。
- 报告是某一时点的可再生产物。
- 细分方向和上市公司是多对多关系。
- 投研结论必须能追溯到 evidence / claim / metric / TODO。
- 更新研究时必须输出变化记录。

## 产品边界

- **Research**：管理证据、研究判断和工作流；不输出买入、卖出、持有或仓位建议。
- **Portfolio**：在本地私有数据库中记录、核对并展示持仓、现金、成本、行情和盈亏事实。
- **Investment Review**：只读消费 Portfolio 事实并写入独立 sidecar；普通复盘为
  `observation_only`，只有当次显式 advice、期限、风险预算和相关仓位约束齐备时才可给出个性化建议。

个人高风险权益账户的十项原则见
[`PERSONAL_HIGH_RISK_EQUITY_STRATEGY_CHARTER.md`](docs/policies/PERSONAL_HIGH_RISK_EQUITY_STRATEGY_CHARTER.md)。
它是人类可读政策，不是机器参数；`C-HUMAN-005` 仍为 `pending` / `null`。

## 当前阶段

当前处于 **P1.6：workflow buildout / 进入 P2 前的工作流制度化**。

P1.6 是项目 buildout 标签，不是单次 workflow 的运行状态。跨 run 的当前选择以 [`config/r5_readout_canonical_index.yaml`](config/r5_readout_canonical_index.yaml) 的 `current_runs` 为唯一 pointer；从其中的 `state_path` 读取 run 状态，从 `readout_path` 打开对应的人类投影。README 不复制当前 workflow ID 或 status；[`R5_READOUT_CANONICAL_INDEX.md`](reports/p1_6/R5_READOUT_CANONICAL_INDEX.md) 只是历史 R5/Patch/Bundle 目录。

Pointer 可能指向已做 hash 绑定的兼容 run，其 readout 会保留当时的字段；新 run 的写入结构以 `research-orchestrator` 的 workflow-state template/schema 为准，不反向改写旧 run。

P1.6 的重点是：

1. 固化 `docs/workflows/RESEARCH_WORKFLOW.md` 作为唯一全局 workflow kernel。
2. 启用 `research-orchestrator` 作为总编排入口。
3. 补强 evidence ingest、stock deep dive、mapping、quality review 等下层契约。
4. 通过 stock-led、segment-led、segment-stock interlock 调试。
5. 执行 P2 readiness gate，只判断是否进入 limited P2 pilot。

P1.6 Research buildout 不做：扩展新细分、P2 横向比较、批量扩大公司池、自动交易、
实时行情监控或买卖建议生成。独立 Portfolio / Investment Review 不改变这一 Research 阶段边界。

## 文档入口

| 文件 | 用途 |
|---|---|
| `AGENTS.md` | Codex 项目级长期规则和投研纪律。 |
| `docs/index.md` | 文档总索引；只导航，不承载事实源正文。 |
| `docs/project/PROJECT_CHARTER.md` | 项目目标、边界、路线图和暂停点。 |
| `docs/architecture/WORKSPACE_STRUCTURE.md` | 目录结构、文件归位和命名规则。 |
| `docs/architecture/RESEARCH_OBJECT_MODEL.md` | Segment、Company、Evidence、Claim、Metric 等对象模型。 |
| `docs/policies/EVIDENCE_AND_CITATION_POLICY.md` | 证据、引用、来源等级和新鲜度规则。 |
| `docs/policies/QUALITY_GUARDRAILS.md` | 质量检查、反幻觉、反证和 no-advice 纪律。 |
| `docs/policies/PERSONAL_HIGH_RISK_EQUITY_STRATEGY_CHARTER.md` | 已确认的人类可读定性章程；不是机器参数。 |
| `docs/workflows/README.md` | workflow 文档入口。 |
| `docs/workflows/RESEARCH_WORKFLOW.md` | 唯一全局 workflow kernel；定义 `workflow_type`、global stage、global gate、backflow decision。 |
| `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | `research-orchestrator` 运行时规范；消费全局接口，不重新定义全局接口。 |
| `docs/workflows/DATA_LAYER_WORKFLOW.md` | 数据层 source adapter、manifest、candidate、data pack 边界。 |
| `config/r5_readout_canonical_index.yaml` | `current_runs` 选择跨 run 的当前 state/readout；这是 current pointer 唯一 owner。 |
| `reports/workflow_runs/<workflow_id>/` | 每个 run 的 state、readout 与审计产物；当前路径必须从 `current_runs` 解析，不在 README 手写。 |
| `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md` | 历史 R5/Patch/Bundle readout 目录；不是 current pointer。 |
| `.agents/skills/stock-deep-dive/references/report_production_profile.md` | 个股报告生产 profile；属于 `stock-deep-dive` 执行细节。 |
| `.agents/skills/portfolio-tracker/SKILL.md` | Portfolio 私有账务工具边界。 |
| `.agents/skills/investment-review/SKILL.md` | Investment Review、`observation_only` 与 advice 输入门禁。 |
| `docs/playbooks/PORTFOLIO_TRACKER.md` | Portfolio CLI、账务口径和本地看板操作。 |
| `docs/meta/DOC_OWNERSHIP_MATRIX.md` | 文档职责边界和去重矩阵。 |

`docs/plans/`、`docs/logs/`、`docs/codex_tasks/` 是阶段性材料，不作为当前事实源阅读路径。

## Skills

P1.6 后，`research-orchestrator` 是总编排入口，下层 skills 执行具体研究动作：

```text
research-orchestrator
evidence-ingest
segment-research
company-universe
segment-company-mapping
stock-deep-dive
quality-review
refresh-research
compare-segments
compare-stocks
memo-writer
```

个股深度研究统一使用 `stock-deep-dive`。如果存在未启用或待合并的旧 skill 目录，应先按 `.codex/config.toml` 和 `docs/meta/DOC_OWNERSHIP_MATRIX.md` 判断是否仍可路由；不要让历史 skill 覆盖当前主工作流。

`portfolio-tracker` 和 `investment-review` 是显式调用的独立产品 utility，不属于
`research-orchestrator` 的 workflow 类型或 P2 readiness 路由。通用本地入口为：

```powershell
.\scripts\start_portfolio_dashboard.ps1
.\scripts\start_investment_review.ps1 status
```

## 最小使用方式

```text
$research-orchestrator 启动个股优先闭环：002837 英维克。
目标：消费 evidence-ingest 产物，输出 stock package、segment_exposure、quality gate 和 close readout。
```

```text
$research-orchestrator 启动细分到个股闭环：AI服务器液冷。
目标：输出 segment package、company_universe、exposure mapping、stock sample 和 quality readout。
```

## 研究边界

Research 产品可以输出研究框架、证据地图、风险清单、评分卡、观察清单、情景假设和 refresh log。

Research 产出不输出直接买卖建议、仓位建议、保证收益判断或自动交易指令。

Portfolio 只输出账务和行情事实。Investment Review 缺少当次显式 advice、期限、
风险预算或相关仓位约束时，必须保持 `observation_only`，且 `action` 与
`target_position` 均为空。任何产品都不执行订单。
