# Workflows — 永久工作流文档入口

`docs/workflows/` 是 A-share Research OS 的永久工作流事实源目录。它说明系统在日常研究中如何运转，而不是记录某个建设阶段的临时计划。

## 本目录负责回答

1. 用户说“研究一个细分 / 深挖一个股票 / 刷新已有研究”时，系统如何判断 workflow 类型。
2. `research-orchestrator` 如何编排下层 skills。
3. 每个 workflow 阶段的输入、输出、质量门和回写关系是什么。
4. 细分研究和个股研究如何既独立运行，又通过 evidence、claims、metrics、`segment_company_exposure` 互相连接。
5. 进入 P2 比较前，哪些基础闭环必须先通过。

## 本目录不负责

- 项目路线图。
- P0 / P1 / P1.5 / P2 / P3 阶段计划。
- 单次执行 readout。
- 某个细分或个股的研究报告。
- 日常命令速查。

阶段计划放在 `docs/plans/`；日常提示放在 `docs/playbooks/`；执行日志放在 `docs/logs/`。

## 文件列表

| 文件 | 定位 | 是否事实源 | 上位文件 |
|---|---|---:|---|
| `RESEARCH_WORKFLOW.md` | 永久总工作流：workflow 类型、阶段、交接资产、细分/个股关系、P2 前置条件 | 是 | `AGENTS.md` |
| `WORKFLOW_ORCHESTRATION_SPEC.md` | `research-orchestrator` 如何分类、建 run、路由 skill、生成 handoff、检查门禁 | 是 | `RESEARCH_WORKFLOW.md` |
| `DATA_LAYER_WORKFLOW.md` | 数据层如何发现、拉取、归档、标准化、候选化和交接 | 是 | `RESEARCH_WORKFLOW.md` |
| `STOCK_REPORT_PRODUCTION_WORKFLOW.md` | 样例级个股报告生产流程；服务 stock-first / R4 readiness，不替代 `stock-deep-dive` | 是 | `RESEARCH_WORKFLOW.md` |

未来如果继续细化 workflow，可以新增：

```text
SEGMENT_RESEARCH_WORKFLOW.md
STOCK_DEEP_DIVE_WORKFLOW.md
SEGMENT_STOCK_INTERLOCK_WORKFLOW.md
REFRESH_RESEARCH_WORKFLOW.md
COMPARISON_READINESS_WORKFLOW.md
```

新增文件必须以 `RESEARCH_WORKFLOW.md` 为上位事实源，并同步更新本 README 与 `docs/index.md`。

## 与 skills 的关系

```text
docs/workflows/RESEARCH_WORKFLOW.md
    = 事实源：说明系统如何运转。

.agents/skills/research-orchestrator/SKILL.md
    = 执行入口：按事实源路由下层 skills。

.agents/skills/<lower-skill>/SKILL.md
    = 下层执行契约：完成证据导入、细分研究、个股研究、质量检查等动作。
```

`research-orchestrator` 不是万能研究员。它只负责编排、状态、路由、门禁和 readout；具体研究动作必须交给下层 skills。

## 旧 skill 名称处理

如果历史文档或目录中出现 `stock-research-analyst`、`stock-report-writer` 等拆分式个股技能名称，默认视为已合并到 `stock-deep-dive` 的待归档参考。

当前主路径应优先使用：

```text
research-orchestrator
→ evidence-ingest
→ stock-deep-dive
→ segment-company-mapping
→ quality-review
→ research-orchestrator close readout
```

只有当 `.codex/config.toml` 明确启用某个旧 skill，并且当前 workflow 文档仍引用它时，才允许路由到该 skill。

## 版本纪律

当 workflow 发生结构性变化时，同步更新：

1. `RESEARCH_WORKFLOW.md` 的 workflow 定义或阶段表。
2. `WORKFLOW_ORCHESTRATION_SPEC.md` 的路由矩阵和质量门。
3. `.agents/skills/research-orchestrator/SKILL.md` 的执行规则。
4. 相关下层 skill 的 `SKILL.md`、`references/`、`scripts/` 和样例资产。
5. `docs/index.md` 与 `docs/meta/DOC_OWNERSHIP_MATRIX.md`。
