# Operating Playbook — 快速入口与常用命令索引

> 本文件不是工作流事实源，也不定义 P1/P2/P3 阶段细节。永久 workflow kernel 见 `docs/workflows/RESEARCH_WORKFLOW.md`；orchestrator runtime contract 见 `.agents/skills/research-orchestrator/references/orchestration_contract.md`。

## 1. 文档入口

| 需求 | 入口 |
|---|---|
| 查项目级纪律、证据规则、禁止事项 | `AGENTS.md` |
| 查文档总目录 | `docs/index.md` |
| 查永久工作流定义 | `docs/workflows/RESEARCH_WORKFLOW.md` |
| 查 workflow run、handoff 和编排 runtime | `.agents/skills/research-orchestrator/references/orchestration_contract.md` |
| 查当前 P1.6 建设计划 | `docs/plans/P1_6_WORKFLOW_BUILDOUT_PLAN.md` |
| 查 P1.6 已完成基础设施记录 | `docs/logs/2026-07-02_p1_6_workflow_foundation_log.md` |

## 2. 常见任务入口

| 任务 | 建议入口 | 主要产出 |
|---|---|---|
| 启动、续跑、诊断或收尾完整 workflow | `$research-orchestrator` | workflow run、handoff、quality gate、readout |
| 导入公告、年报、PDF、CSV | `$evidence-ingest` | raw file、processed text、evidence_manifest |
| 研究一个细分 | `$research-orchestrator` 或 `$segment-research` | segment report、company_universe、scorecard、evidence_map |
| 找细分相关 A 股公司 | `$company-universe` | company_universe.csv、exposure candidates |
| 维护细分-公司映射 | `$segment-company-mapping` | segment_company_exposure |
| 做一个个股深度 | `$research-orchestrator` 或 `$stock-deep-dive` | stock deep dive、segment_exposure、evidence_map |
| 更新已有研究 | `$refresh-research` | refresh_log、stale_claims、reports_to_regenerate |
| 检查质量 | `$quality-review` | evidence gaps、口径问题、反证缺失、issue list |
| 写观察备忘录 | `$memo-writer` | investment_memo、watchlist note、thesis note |
| 检查能否进入 P2 | `$research-orchestrator` | comparison_readiness_gate、P2 readiness readout |

## 3. 常用命令模板

### 3.1 启动细分到个股闭环

```text
$research-orchestrator 启动细分到个股闭环：<segment_name>，深度=standard。
要求：创建或更新 workflow run，路由下层 skills，保留 handoff、quality gate 和 workflow readout。
```

### 3.2 启动个股优先闭环

```text
$research-orchestrator 启动个股优先闭环：<stock_code> <company_name>。
要求：先确认公司身份，再识别 linked_segments，输出 segment_exposure，并说明是否需要回写细分资产。
```

### 3.3 导入或登记证据

```text
$evidence-ingest 登记 <source_path>。
要求：生成 evidence_id，记录 source_type、publisher、date、hash、source_path，并标记 reliability。
```

### 3.4 检查质量

```text
$quality-review 检查 <artifact_path>。
重点检查 evidence_id、claim_type、metric 口径、exposure 证据、反证、过期证据和直接投资建议风险。
```

### 3.5 刷新已有研究

```text
$refresh-research 更新 <segment_id 或 stock_code>。
要求：只输出变化；标记 stale / superseded / contradicted claims；不要静默重写旧报告。
```

## 4. Workflow Run 快速检查

完整 workflow run 通常应包含：

```text
reports/workflow_runs/<workflow_id>/workflow_state.yaml
reports/workflow_runs/<workflow_id>/run_log.md
reports/workflow_runs/<workflow_id>/artifact_manifest.csv
reports/workflow_runs/<workflow_id>/open_todos.csv
reports/workflow_runs/<workflow_id>/quality_gate_report.md
reports/workflow_runs/<workflow_id>/workflow_readout.md
reports/workflow_runs/<workflow_id>/handoffs/
```

如果只是一次简短诊断，可以不创建运行目录，但最终回答必须说明“未创建 workflow run”。

## 5. 质量检查触发点

以下情况必须调用或执行质量检查：

- 新增或更新细分报告前；
- 新增或更新个股报告前；
- 修改 scorecard 或 exposure 前；
- 纳入、移出或调整 watchlist 前；
- 输出 memo 前；
- 发现证据冲突、口径冲突或 stale claims 时；
- 准备进入 P2 readiness gate 时。

## 6. Watchlist 更新纪律

纳入 watchlist 需要写清：

```text
对象
纳入原因
支持证据
主要不确定性
验证指标
触发条件
下次复核日期
```

移出 watchlist 需要写清：

```text
对象
移出原因
被推翻的假设
新增反证
损失/机会成本复盘
后续是否归档
```

## 7. 日常禁区

- 不编造数据、证据、来源、日期、页码或公司暴露。
- 不把聊天内容直接当成证据。
- 不因市场热度提高 exposure_score 或 watchlist 优先级。
- 不用评分卡替代投资判断。
- 不输出买入、卖出、持有等直接交易指令。
- 不静默覆盖旧报告或 raw evidence。
