# Project Charter — A-share Research OS

## 1. 项目使命

A-share Research OS 是一个证据驱动的 A 股投研工作区。它的目标不是一次性生成漂亮研报，而是建立一个可沉淀、可追溯、可更新、可横向比较、可复盘的研究操作系统。

一句话目标：

> 用标准化 skills 固化“怎么研究”，用 evidence / claims 固化“为什么这么判断”，用 segment-company 多对多映射解决 A 股跨细分问题，用 refresh / quality 机制维护研究长期有效性。

---

## 2. 项目边界

### 2.1 系统负责

- 维护研究对象：细分、公司、股票、证据、事实、指标、报告、假设、跟踪项。
- 维护证据纪律：原始证据不可覆盖，关键结论必须可追溯。
- 维护投研流程：细分研究、公司池、个股深度、横向比较、刷新维护、质量审查。
- 维护研究产物：报告、评分卡、对比矩阵、证据地图、观察清单、备忘录、复盘。
- 维护不确定性：缺失数据、低置信度、反证、风险、过期结论必须显性化。

### 2.2 系统不负责

- 不生成直接买入、卖出、持有建议。
- 不承诺自动交易。
- 不在 P0 实现复杂数据库。
- 不在 P0 做全市场扫描。
- 不在 P0 做自动估值模型。
- 不在 P0 做实时行情监控。
- 不把管理层表述、券商预测、市场传闻直接当成事实。

---

## 3. 核心原则

| 原则 | 说明 |
|---|---|
| 证据优先 | 报告不是唯一真相；证据、claims、metrics 才是核心资产 |
| 原始证据不可覆盖 | `data/raw/` 下文件只新增不修改 |
| 结论可追溯 | 关键结论必须引用 `evidence_id`、`claim_id` 或 `metric_id` |
| 类型分离 | 明确区分事实、估计、推断、管理层表述、第三方观点和研究观点 |
| 多对多映射 | 一个公司可以属于多个细分，一个细分可以对应多家公司 |
| 更新有痕 | 新证据出现时输出 change log，不静默重写 |
| 反证显性化 | 重要结论必须配套风险、反证或缺失项 |
| 不伪精确 | 评分是比较框架，不是交易信号 |

---

## 4. 建设阶段

## P0：工作区骨架与研究纪律

目标：让 Codex 和人都清楚项目规则、目录、对象、证据纪律和 skills 边界。

交付物：

```text
AGENTS.md
README.md
PROJECT_CHARTER.md
WORKSPACE_STRUCTURE.md
RESEARCH_OBJECT_MODEL.md
EVIDENCE_AND_CITATION_POLICY.md
QUALITY_GUARDRAILS.md
OPERATING_PLAYBOOK.md
docs/plans/plan_template.md
docs/plans/p0_acceptance_checklist.md
.codex/config.toml
```

暂停点：

- 顶层规则清楚。
- 目录结构清楚。
- skills 边界清楚。
- 证据、报告、配置、决策记录有固定位置。
- 不继续加复杂功能。

## P1：最小研究闭环

目标：用一个细分跑通“细分研究 → 公司池 → 1-2 个个股 → 评分 → 观察清单”。

交付物：

```text
reports/segments/<segment_id>/<date>_segment_report.md
reports/segments/<segment_id>/company_universe.csv
reports/segments/<segment_id>/scorecard.yaml
reports/segments/<segment_id>/evidence_map.md
reports/stocks/<stock_code>_<company_slug>/<date>_stock_deep_dive.md
```

暂停点：

- 一个细分方向能被稳定研究。
- 一个公司可以映射到多个细分。
- 报告关键结论可追溯证据。

## P2：比较、评分与研究队列

目标：多个细分、多个个股可以横向比较，并形成 watchlist / research_queue。

交付物：

```text
reports/comparisons/<date>_segment_comparison.md
reports/comparisons/<date>_segment_score_matrix.csv
reports/comparisons/<date>_stock_comparison.md
config/watchlist.yaml
decisions/watchlist_changes.md
```

暂停点：

- 至少 3-5 个细分可比较。
- 同一细分下多个个股可比较。
- watchlist 能解释纳入与剔除理由。

## P3：更新、维护与复盘

目标：新证据驱动旧结论更新，形成长期维护机制。

交付物：

```text
reports/refresh/<date>_refresh_log.md
reports/refresh/stale_claims.csv
reports/refresh/updated_scorecards.yaml
reports/refresh/reports_to_regenerate.yaml
decisions/postmortems/
```

暂停点：

- 新证据能登记。
- 旧 claims 能标记 stale / superseded / contradicted。
- 更新输出 change log。
- 投资假设有复盘记录。

---

## 5. 模块拆解

| 模块 | 作用 | 对应阶段 |
|---|---|---|
| 工作区底座 | 规则、目录、配置、README、AGENTS.md | P0 |
| 研究对象体系 | Segment、Company、Evidence、Claim、Metric 等 | P0-P1 |
| 证据库体系 | 导入、归档、摘录、状态维护 | P1-P3 |
| 细分研究体系 | 定义、产业链、指标、公司池、评分 | P1 |
| 个股研究体系 | 业务、财务、细分暴露、估值、风险 | P1 |
| 比较体系 | 细分比较、个股比较、优先级排序 | P2 |
| 更新体系 | 新证据、旧结论、评分变化、报告刷新 | P3 |
| 质量体系 | 证据检查、口径检查、反证检查、复盘 | P0-P3 |

---

## 6. 决策纪律

任何纳入 watchlist、提升研究优先级、降低优先级、移除观察对象的动作，都必须记录：

```text
日期
对象
动作
原始假设
新增证据
判断变化
风险变化
下一步验证指标
负责人/备注
```

不要让研究结论只存在于一次对话或一篇报告中。
