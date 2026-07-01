# plan_template.md — 执行计划模板

## 1. 什么时候写计划

以下任务应先写计划再执行：

- 修改顶层规则或目录结构。
- 新增或修改 skill 边界。
- 新增研究对象模型字段。
- 新增证据导入流程。
- 生成一个完整细分研究包。
- 生成一个个股深度研究包。
- 做多个细分或个股横向比较。
- 刷新已有研究并影响旧结论。
- 修改 watchlist 或 thesis log。

简单修正错别字、补充说明、调整格式，可以不写完整计划。

---

## 2. 文件命名规则

`docs/plans/` 下的计划文件统一使用英文小写 `snake_case`；计划完成情况放在与 `docs/plans/` 平行的 `docs/logs/`：

- 通用模板：`plan_template.md`
- 阶段计划：`p0_execution_plan.md`、`p1_execution_plan.md`
- 阶段修正计划：`p1_1_revision_plan.md`
- 验收清单：`p0_acceptance_checklist.md`
- 完成情况日志：`docs/logs/YYYY-MM-DD_plan_completion_log.md`
- 阶段记录：`docs/logs/<stage_id>/YYYY-MM-DD_<stage_id>_<record_type>.md`

日志文件的完整规则以 `docs/logs/README.md` 为准。文件名应先写阶段或日期，再写文档类型；中文标题只放在正文标题中，不放在路径中。

---

## 3. 执行计划格式

```md
# Plan: <任务名称>

## 1. 背景
- 任务来源：
- 相关文件：
- 相关对象：
- 当前阶段：P0 / P1 / P2 / P3

## 2. 目标
- 本次要完成什么：
- 不做什么：
- 完成后如何验收：

## 3. 输入
- 用户输入：
- 证据文件：
- 配置文件：
- 既有报告：

## 4. 输出
- 需要新建的文件：
- 需要修改的文件：
- 不应修改的文件：

## 5. 步骤
| Step | 动作 | 产出 | 风险 | 验收 |
|---|---|---|---|---|
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |

## 6. 质量检查
- [ ] 关键结论有 evidence_id / claim_id
- [ ] 事实、估计、推断、观点已区分
- [ ] 原始证据未覆盖
- [ ] 文件放在正确目录
- [ ] 缺失数据已标记 TODO / MISSING
- [ ] 风险和反证已列出
- [ ] 更新任务有 change log
- [ ] 不包含直接买卖建议

## 7. 暂停点
- 完成到什么程度应暂停：
- 哪些事项留到下一阶段：

## 8. Closeout
- 已完成：
- 未完成：
- 需要人工复核：
- 下一步建议：
```

---

## 4. P0 计划模板

```md
# Plan: P0 顶层文件生成

## 目标
建立项目顶层文档，让 Codex 和人都能理解 A-share Research OS 的边界、目录、对象、证据纪律和质量要求。

## 不做
- 不实现数据库。
- 不抓取公告。
- 不生成完整研报。
- 不做估值模型。
- 不做全市场扫描。

## 输出
- AGENTS.md
- README.md
- PROJECT_CHARTER.md
- WORKSPACE_STRUCTURE.md
- RESEARCH_OBJECT_MODEL.md
- EVIDENCE_AND_CITATION_POLICY.md
- QUALITY_GUARDRAILS.md
- OPERATING_PLAYBOOK.md
- plan_template.md
- p0_acceptance_checklist.md

## 验收
- 顶层规则清楚。
- 目录结构清楚。
- 证据纪律清楚。
- skills 边界清楚。
- P0 暂停点清楚。
```

---

## 5. 细分研究计划模板

```md
# Plan: Segment Research — <segment_name>

## 目标
产出一个可追溯、可比较、可更新的细分研究包。

## 输入
- segment_name:
- date_range:
- depth: quick / standard / deep
- focus:

## 输出
- reports/segments/<segment_id>/<date>_segment_report.md
- reports/segments/<segment_id>/company_universe.csv
- reports/segments/<segment_id>/scorecard.yaml
- reports/segments/<segment_id>/evidence_map.md
- reports/segments/<segment_id>/refresh_tasks.yaml

## 步骤
1. 标准化 segment_id。
2. 定义 scope_in / scope_out。
3. 搜索和登记证据。
4. 梳理产业链、需求、供给、利润池。
5. 建立 A 股公司池。
6. 标注 segment-company exposure。
7. 建立关键指标体系。
8. 输出 scorecard。
9. 列出风险、反证和 missing data。
10. 执行 quality-review。
```

---

## 6. 个股研究计划模板

```md
# Plan: Stock Deep Dive — <stock_code> <company_name>

## 目标
产出一个与多个细分方向联动的个股深度研究包。

## 输入
- stock_code:
- company_name:
- linked_segments:
- date_range:

## 输出
- reports/stocks/<stock_code>_<company_slug>/<date>_stock_deep_dive.md
- reports/stocks/<stock_code>_<company_slug>/segment_exposure.yaml
- reports/stocks/<stock_code>_<company_slug>/evidence_map.md
- reports/stocks/<stock_code>_<company_slug>/valuation_scenarios.*

## 步骤
1. 确认公司主体与证券代码。
2. 收集年报、公告、财务数据、调研资料。
3. 拆解业务结构。
4. 建立 linked_segments。
5. 标注 exposure_type、exposure_score、confidence。
6. 分析财务质量。
7. 梳理客户、供应链、产能、订单、募投。
8. 做估值场景和敏感性分析。
9. 列出风险和反证。
10. 执行 quality-review。
```

---

## 7. Refresh 计划模板

```md
# Plan: Refresh Research — <scope>

## 目标
根据新增证据更新既有研究状态，不静默重写旧报告。

## 输入
- watchlist:
- date_range:
- affected_segments:
- affected_companies:

## 输出
- reports/refresh/<date>_refresh_log.md
- reports/refresh/stale_claims.csv
- reports/refresh/updated_scorecards.yaml
- reports/refresh/reports_to_regenerate.yaml

## 步骤
1. 找出新增 evidence。
2. 对比旧 evidence_snapshot。
3. 标记 stale / superseded / contradicted claims。
4. 更新 scorecard。
5. 更新 watchlist 变动建议。
6. 输出 reports_to_regenerate。
7. 执行 quality-review。
```
