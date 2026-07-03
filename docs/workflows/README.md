# Workflows — 永久工作流文档入口

> 本目录是 A-share Research OS 的**永久工作流事实源**。它说明这个研究系统在日常使用中如何运转，而不是记录某个建设阶段的临时计划。

## 1. 本目录的职责

`docs/workflows/` 负责回答这些问题：

1. 用户说“研究一个细分 / 深挖一个股票 / 刷新已有研究”时，系统如何判断工作流类型；
2. 总工作流如何编排下层 skills；
3. 每个工作流阶段的输入、输出、质量门和回写关系是什么；
4. 细分研究和个股研究如何既独立运行，又通过 `segment_company_exposure`、evidence、claims、metrics 互相连接；
5. 进入 P2 比较前，哪些基础闭环必须先通过。

本目录不是：

- 项目路线图；
- P0/P1/P1.5/P2/P3 的阶段计划；
- 单次执行 readout；
- 某个细分或个股的研究报告。

阶段计划放在 `docs/plans/`；日常提示和轻量操作建议可以放在 `docs/playbooks/`；永久工作流事实源放在本目录。

## 2. 文件列表

| 文件 | 定位 | 是否事实源 |
|---|---|---:|
| `RESEARCH_WORKFLOW.md` | 永久总工作流文档：定义工作流类型、阶段、交接资产、细分/个股关系、质量门、P2 前置条件 | 是 |
| `WORKFLOW_ORCHESTRATION_SPEC.md` | 总工作流编排规范：定义 `research-orchestrator` 如何分类、建 run、路由 skill、生成 handoff、检查门禁 | 是 |
| `DATA_LAYER_WORKFLOW.md` | 数据层工作流：定义 source adapter、结构化快照、market context、data packs 和数据层质量门 | 是 |

后续逐个工作流细化时，可继续新增：

```text
SEGMENT_RESEARCH_WORKFLOW.md
STOCK_DEEP_DIVE_WORKFLOW.md
SEGMENT_STOCK_INTERLOCK_WORKFLOW.md
REFRESH_RESEARCH_WORKFLOW.md
COMPARISON_READINESS_WORKFLOW.md
```

这些新增文件仍应放在 `docs/workflows/`，并以 `RESEARCH_WORKFLOW.md` 为上位事实源。

## 3. 与 skill 的关系

永久文档和 skill 的职责分开：

```text
docs/workflows/RESEARCH_WORKFLOW.md
    = 事实源：说明系统如何运转。

.agents/skills/research-orchestrator/SKILL.md
    = 执行入口：用户提出研究请求时，按事实源路由下层 skills。

.agents/skills/<lower-skill>/SKILL.md
    = 下层执行 skill：完成证据导入、细分研究、个股研究、质量检查等具体动作。
```

Codex 不能把 `research-orchestrator` 当作万能研究员。它只负责编排、状态、路由、门禁和 readout；具体研究动作必须交给下层 skills。

## 4. 推荐加入 docs/index.md 的条目

```md
## Workflows
- workflows/README.md
- workflows/RESEARCH_WORKFLOW.md
- workflows/WORKFLOW_ORCHESTRATION_SPEC.md
- workflows/DATA_LAYER_WORKFLOW.md
```

## 5. 版本纪律

当工作流发生结构性变化时，应同步更新：

1. `RESEARCH_WORKFLOW.md` 中的工作流定义或阶段表；
2. `WORKFLOW_ORCHESTRATION_SPEC.md` 中的路由矩阵和质量门；
3. `.agents/skills/research-orchestrator/SKILL.md` 中的执行规则；
4. 必要时更新下层 skill 的 `SKILL.md`、`references/`、`scripts/` 和样例资产。
