# P0 Acceptance Checklist — P0 验收清单

## 1. 验收目标

P0 的目标是搭建一个守纪律、可扩展、可被 Codex 理解的 A 股投研工作区骨架。

P0 完成后不要求生成研报，不要求自动化，不要求数据库，不要求抓取公告。

---

## 2. 顶层文件

- [x] `AGENTS.md` 已创建，并写明项目角色、原则、文件归位、证据纪律和输出要求。
- [x] `README.md` 已创建，并说明项目定位、路线图、目录结构和使用方式。
- [x] `PROJECT_CHARTER.md` 已创建，并说明目标、范围、非目标和阶段暂停点。
- [x] `WORKSPACE_STRUCTURE.md` 已创建，并说明目录结构、文件位置和命名规则。
- [x] `RESEARCH_OBJECT_MODEL.md` 已创建，并说明 Segment、Company、Evidence、Claim、Metric 等对象。
- [x] `EVIDENCE_AND_CITATION_POLICY.md` 已创建，并说明证据 ID、来源等级、引用和刷新规则。
- [x] `QUALITY_GUARDRAILS.md` 已创建，并说明质量检查和反幻觉规则。
- [x] `OPERATING_PLAYBOOK.md` 已创建，并说明 P0-P3 常用流程。
- [x] `plan_template.md` 已创建，并提供复杂任务计划模板。
- [x] `p0_acceptance_checklist.md` 已创建。

---

## 3. Codex 配置

- [x] `.codex/config.toml` 已创建。
- [x] 配置中列出 repo skills 路径。
- [x] 配置中不包含密钥、账户、token 或敏感信息。
- [x] 项目可被识别为独立 workspace。

---

## 4. 目录结构

- [x] `.agents/skills/` 目录已规划。
- [x] `config/` 目录已规划。
- [x] `data/raw/` 目录已规划。
- [x] `data/processed/` 目录已规划。
- [x] `data/db/` 目录已规划。
- [x] `data/manifests/` 目录已规划。
- [x] `templates/` 目录已规划。
- [x] `reports/segments/` 目录已规划。
- [x] `reports/stocks/` 目录已规划。
- [x] `reports/comparisons/` 目录已规划。
- [x] `reports/refresh/` 目录已规划。
- [x] `reports/memos/` 目录已规划。
- [x] `decisions/` 目录已规划。
- [x] `tests/` 目录已规划。

---

## 5. Skills 边界

P0 不要求 skill 完整实现，但必须明确边界。

- [x] `evidence-ingest` 的用途、输入、输出、非目标已定义。
- [x] `segment-research` 的用途、输入、输出、非目标已定义。
- [x] `company-universe` 的用途、输入、输出、非目标已定义。
- [x] `segment-company-mapping` 的用途、输入、输出、非目标已定义。
- [x] `stock-deep-dive` 的用途、输入、输出、非目标已定义。
- [x] `compare-segments` 的用途、输入、输出、非目标已定义。
- [x] `compare-stocks` 的用途、输入、输出、非目标已定义。
- [x] `refresh-research` 的用途、输入、输出、非目标已定义。
- [x] `quality-review` 的用途、输入、输出、非目标已定义。
- [x] `memo-writer` 的用途、输入、输出、非目标已定义。

---

## 6. 研究对象体系

- [x] `Segment` 定义清楚。
- [x] `Company` 定义清楚。
- [x] `Security` 定义清楚。
- [x] `Evidence` 定义清楚。
- [x] `Claim` 定义清楚。
- [x] `Metric` 定义清楚。
- [x] `Report` 定义清楚。
- [x] `Thesis` 定义清楚。
- [x] `WatchItem` 定义清楚。
- [x] `segment_company_exposure` 字段和 scoring 逻辑清楚。

---

## 7. 证据纪律

- [x] 原始证据不可覆盖规则已写入 `AGENTS.md`。
- [x] `data/raw/` 与 `data/processed/` 的区别清楚。
- [x] `evidence_id` 命名规则清楚。
- [x] `claim_id` 使用场景清楚。
- [x] 证据来源等级 A/B/C/D 清楚。
- [x] `fresh` / `stale` / `superseded` / `contradicted` / `low_confidence` 状态清楚。
- [x] 缺失数据用 TODO / MISSING / LOW_CONFIDENCE 标记。

---

## 8. 输出纪律

- [x] 细分研究包产物清楚。
- [x] 个股研究包产物清楚。
- [x] 对比研究包产物清楚。
- [x] 刷新研究包产物清楚。
- [x] 投资备忘录和 watchlist 变动记录位置清楚。
- [x] 不直接输出买卖建议的规则清楚。

---

## 9. 质量纪律

- [x] 事实、估计、推断、管理层表述、第三方观点和研究观点分离。
- [x] material claim 必须引用证据。
- [x] 指标口径必须写明。
- [x] 反证和风险必须列出。
- [x] 冲突证据必须并列呈现。
- [x] 更新研究必须输出 change log。
- [x] 评分不是交易信号。

---

## 10. P0 暂停条件

完成以下条件后，P0 应暂停，不继续扩功能：

- [x] Codex 进入项目后能理解这是 A 股投研工作区。
- [x] 原始证据、处理数据、报告、配置、决策记录都有固定位置。
- [x] 细分和公司多对多关系已经写清楚。
- [x] 关键结论必须追溯证据的规则已经写清楚。
- [x] skills 作为投研动作而非报告生成器的边界已经写清楚。
- [x] P1 可以选择一个细分开始跑最小闭环。

---

## 11. P0 不应继续做的事

- [x] 不实现复杂数据库。
- [x] 不自动抓取公告。
- [x] 不批量研究 20 个细分。
- [x] 不做自动估值模型。
- [x] 不做行情监控。
- [x] 不做交易策略或组合优化。
- [x] 不把 P0 扩展成完整投研 Agent。

---

## 12. 验收结论

填写：

```text
验收日期：2026-07-01
验收人：Codex
P0 状态：通过
主要缺口：无 P0 阻塞项；P1 需要导入真实证据并跑一个细分最小闭环。
下一步：进入 P1；先选择一个细分方向，不继续扩展 P0 功能。
```
