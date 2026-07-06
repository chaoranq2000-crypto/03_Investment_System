# Workflows — 工作流文档入口

`docs/workflows/` 说明 A-share Research OS 在日常研究中如何运转。它不是阶段计划目录，也不是某次执行日志目录。

## Canonical boundary

只有一个文件定义全局 workflow kernel：

```text
docs/workflows/RESEARCH_WORKFLOW.md
```

它唯一拥有：

```text
workflow_type
global stage_id
global gate_id
backflow_decision
P2 readiness global criteria
```

其他 workflow 文件只能消费这些接口，不能重新定义。

## 文件列表

| 文件 | 定位 | 是否定义全局接口 |
|---|---|---:|
| `RESEARCH_WORKFLOW.md` | 全局 workflow kernel。定义 workflow 类型、阶段、交接资产、细分/个股关系、gate、P2 前置条件。 | 是 |
| `WORKFLOW_ORCHESTRATION_SPEC.md` | `research-orchestrator` 如何分类、建 run、路由 skill、生成 handoff、调度门禁。 | 否 |
| `DATA_LAYER_WORKFLOW.md` | 数据层如何发现、拉取、归档、标准化、候选化和交接；可定义 `DL-*` 局部检查。 | 否 |
| `STOCK_REPORT_PRODUCTION_WORKFLOW.md` | 兼容性指针。活跃 report production profile 已迁到 `stock-deep-dive/references/`。 | 否 |

## 与 skills 的关系

```text
docs/workflows/RESEARCH_WORKFLOW.md
  = 事实源：说明系统如何运转，并定义全局接口。

.agents/skills/research-orchestrator/SKILL.md
  = 执行入口：按事实源路由下层 skills。

.agents/skills/<skill>/SKILL.md
  = 下层执行契约：完成证据导入、细分研究、个股研究、质量检查等动作。

.agents/skills/<skill>/references/*
  = 字段、模板、局部 profile、局部子检查。
```

`research-orchestrator` 不是万能研究员。它只负责编排、状态、路由、门禁调度和 readout；具体研究动作必须交给下层 skills。

## 局部步骤命名

全局 gate 只能使用 `G0` 到 `G10`。

局部步骤或子检查必须使用 skill-local 前缀：

```text
DL-*   data layer local checks
SDD-*  stock-deep-dive local steps
QR-*   quality-review local subchecks
RP-*   report-production profile steps
```

## 个股报告生产 profile

个股分析包构建和报告写作已经统一合并到 `stock-deep-dive`。

当前主路径：

```text
research-orchestrator
→ evidence-ingest
→ stock-deep-dive
→ segment-company-mapping
→ quality-review
→ research-orchestrator close readout
```

个股报告生产细节放在：

```text
.agents/skills/stock-deep-dive/references/report_production_profile.md
```

不要把它升级为平级 workflow。

## 版本纪律

当 workflow 发生结构性变化时，按顺序更新：

1. `RESEARCH_WORKFLOW.md` 的 canonical interface。
2. `WORKFLOW_ORCHESTRATION_SPEC.md` 的运行时消费逻辑。
3. 相关 skill 的 `SKILL.md` 或 `references/`。
4. `docs/index.md` 与 `docs/meta/DOC_OWNERSHIP_MATRIX.md`。
5. `scripts/check_doc_drift.py` 的校验规则。
