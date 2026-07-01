# Operating Playbook — 日常使用手册

## 1. 使用原则

本项目的日常工作流按顺序推进：

```text
先定规则
再定对象
再定证据
再定模板
再定 skills 边界
跑通一个细分
跑通一只个股
再做多个细分比较
再做多个个股比较
最后做更新、复盘和规模化
```

P0 阶段只搭骨架，不追求自动化。

---

## 2. 常见任务与入口

| 任务 | 建议入口 | 主要产出 |
|---|---|---|
| 导入公告、年报、PDF、CSV | `$evidence-ingest` | raw file、processed text、evidence_manifest |
| 研究一个细分 | `$segment-research` | segment_report、company_universe、scorecard、evidence_map |
| 找细分相关 A 股公司 | `$company-universe` | company_universe.csv、exposure candidates |
| 维护细分-公司映射 | `$segment-company-mapping` | segment_exposure.yaml / CSV |
| 做一个个股深度 | `$stock-deep-dive` | stock_deep_dive、segment_exposure、evidence_map |
| 比较多个细分 | `$compare-segments` | segment_comparison、score_matrix |
| 比较多个个股 | `$compare-stocks` | stock_comparison、score_matrix |
| 更新已有研究 | `$refresh-research` | refresh_log、stale_claims、reports_to_regenerate |
| 检查质量 | `$quality-review` | evidence gaps、口径问题、反证缺失 |
| 写观察备忘录 | `$memo-writer` | investment_memo、watchlist note、thesis note |

---

## 3. P0 工作流

P0 目标：让项目可被 Codex 和人稳定理解。

### 3.1 执行动作

1. 放置顶层文档。
2. 建立 `.codex/config.toml`。
3. 建立 `.agents/skills/*/SKILL.md` 空壳。
4. 建立 `config/` YAML 空壳。
5. 建立 `templates/` Markdown 模板。
6. 建立 `data/`、`reports/`、`decisions/` 目录。
7. 根据 `docs/plans/p0_acceptance_checklist.md` 验收。

### 3.2 暂停条件

完成以下即可暂停：

```text
AGENTS.md 清楚
README.md 清楚
目录结构清楚
skills 边界清楚
证据与质量规则清楚
P0 验收清单通过
```

不要在 P0 继续实现自动抓取、数据库、估值或批量研究。

---

## 4. P1 最小闭环工作流

选择一个细分，例如：

```text
AI服务器液冷
CPO
机器人丝杠
先进封装
固态电池设备
```

### 4.1 输入示例

```text
$segment-research 调研“AI服务器液冷”，深度=standard。
要求：
1. 明确细分定义、scope_in、scope_out；
2. 梳理产业链位置、需求驱动、供给格局和利润池；
3. 找出 A 股相关公司池；
4. 区分 revenue / product / technology / narrative 暴露；
5. 输出 scorecard、evidence_map 和 refresh_tasks；
6. 所有关键结论必须引用 evidence_id 或标记 TODO。
```

### 4.2 输出检查

```text
reports/segments/<segment_id>/<date>_segment_report.md
reports/segments/<segment_id>/company_universe.csv
reports/segments/<segment_id>/scorecard.yaml
reports/segments/<segment_id>/evidence_map.md
```

### 4.3 进入个股

```text
$stock-deep-dive 调研 <stock_code>，关联细分包括 <segment_id>。
要求：业务拆分、财务质量、细分暴露、客户供应链、估值场景、风险和反证清单。
```

---

## 5. P2 比较工作流

### 5.1 细分比较

```text
$compare-segments 对比：
- AI服务器液冷
- CPO
- 先进封装
- 机器人丝杠

维度：市场空间、增速、渗透率阶段、A股纯度、业绩兑现度、估值拥挤度、催化剂、风险、证据质量。
```

输出：

```text
reports/comparisons/<date>_segment_comparison.md
reports/comparisons/<date>_segment_score_matrix.csv
config/watchlist.yaml 更新建议
decisions/watchlist_changes.md 更新记录
```

### 5.2 个股比较

```text
$compare-stocks 比较 <segment_id> 下的公司：
- 300xxx 公司A
- 688xxx 公司B
- 002xxx 公司C

维度：细分收入占比、业绩弹性、毛利率、客户质量、订单可见度、技术壁垒、财务质量、估值、风险。
```

---

## 6. P3 更新工作流

```text
$refresh-research 更新 watchlist 中所有 active 项。
要求：
1. 找出新增 evidence；
2. 标记 stale / superseded / contradicted claims；
3. 输出 scorecard 变化；
4. 输出 watchlist 变动建议；
5. 输出 reports_to_regenerate；
6. 不要静默重写旧报告。
```

输出：

```text
reports/refresh/<date>_refresh_log.md
reports/refresh/stale_claims.csv
reports/refresh/updated_scorecards.yaml
reports/refresh/reports_to_regenerate.yaml
```

---

## 7. Quality-review 调用时机

以下情况必须调用或执行质量检查：

- 新增细分报告前
- 新增个股报告前
- 修改 scorecard 前
- 纳入 watchlist 前
- 输出 memo 前
- 更新旧报告后
- 发现证据冲突时
- 研究对象涉及高不确定性或高市场热度时

示例：

```text
$quality-review 检查 reports/segments/ai_server_liquid_cooling/2026-06-30_segment_report.md。
重点检查 evidence_id、claim_type、收入/订单/产能口径、反证、过期证据和直接投资建议风险。
```

---

## 8. Watchlist 更新纪律

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

---

## 9. 每周维护建议

每周可以执行一次轻量维护：

1. 检查 watchlist 是否有新证据。
2. 检查是否有报告进入 stale 状态。
3. 检查是否有新公告影响 company exposure。
4. 更新 `decisions/watchlist_changes.md`。
5. 对重大变化输出 refresh log。

---

## 10. 不做事项

日常使用中也要避免：

- 为了回答问题临时编造数据。
- 把聊天内容直接当成证据。
- 因为热度高就提高 exposure_score。
- 无证据提高或降低 watchlist 优先级。
- 用评分直接替代投资判断。
- 静默覆盖旧报告。
