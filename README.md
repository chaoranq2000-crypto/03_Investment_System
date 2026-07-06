# A-share Research OS / A股投研工作区

> 这是一个证据驱动的 A 股投研工作区，不是自动交易系统，也不直接提供买入、卖出或持有建议。

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

## 当前阶段

当前处于 **P1.6：workflow buildout / 进入 P2 前的工作流制度化**。

P1.5：pre-P2 hardening 已作为前序加固阶段完成；当前 P1.6 在此基础上固化工作流事实源和执行入口。

P1.6 的重点是：

1. 固化 `docs/workflows/` 永久工作流事实源。
2. 启用 `research-orchestrator` 作为总编排入口。
3. 补强 evidence ingest、stock deep dive、mapping、quality review 等下层契约。
4. 通过 stock-led、segment-led、segment-stock interlock 调试。
5. 执行 P2 readiness gate，只判断是否进入 limited P2 pilot。

P1.6 不做：扩展新细分、P2 横向比较、批量扩大公司池、自动交易、实时行情监控或买卖建议生成。

## 文档入口

| 文件 | 用途 |
|---|---|
| `AGENTS.md` | Codex 项目级长期规则和投研纪律 |
| `docs/index.md` | 文档总索引 |
| `docs/project/PROJECT_CHARTER.md` | 项目目标、边界、路线图和暂停点 |
| `docs/architecture/WORKSPACE_STRUCTURE.md` | 目录结构、文件归位和命名规则 |
| `docs/architecture/RESEARCH_OBJECT_MODEL.md` | Segment、Company、Evidence、Claim、Metric 等对象模型 |
| `docs/policies/EVIDENCE_AND_CITATION_POLICY.md` | 证据、引用、来源等级和新鲜度规则 |
| `docs/policies/QUALITY_GUARDRAILS.md` | 质量检查、反幻觉、反证和 no-advice 纪律 |
| `docs/workflows/README.md` | 永久工作流文档入口 |
| `docs/workflows/RESEARCH_WORKFLOW.md` | 唯一 global workflow kernel |
| `.agents/skills/research-orchestrator/references/orchestration_contract.md` | `research-orchestrator` runtime、handoff 和 readout contract |
| `docs/workflows/DATA_LAYER_WORKFLOW.md` | 数据层工作流和 source adapter 边界 |
| `.agents/skills/stock-deep-dive/references/report_production_profile.md` | 样例级个股报告生产 profile |
| `docs/meta/DOC_OWNERSHIP_MATRIX.md` | 文档职责边界，防止重复和冲突 |

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

个股深度研究统一使用 `stock-deep-dive`；如出现新的 `stock-*` 技能目录，应先按 `.codex/config.toml` 和 `docs/meta/DOC_OWNERSHIP_MATRIX.md` 判断是否属于当前主工作流。

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

本项目可以输出研究框架、证据地图、风险清单、评分卡、观察清单、情景假设和 refresh log。

本项目不输出直接买卖建议、仓位建议、保证收益判断或自动交易指令。
