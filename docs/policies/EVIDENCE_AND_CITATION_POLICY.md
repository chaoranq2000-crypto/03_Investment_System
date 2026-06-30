# Evidence and Citation Policy — 证据与引用纪律

## 1. 目标

本文件定义 A-share Research OS 的证据、引用、证据状态和刷新规则。

核心目标：

> 让每一个关键结论都能回答：它来自哪里？证据是什么？口径是什么？是否过期？是否存在反证？

---

## 2. 什么是 evidence

Evidence 指可以支撑或反驳研究结论的原始或结构化资料，包括：

- 年报、半年报、季报
- 临时公告、交易所问询、监管文件
- 招股书、募集说明书、定增/可转债文件
- 政策文件、统计局数据、行业协会数据
- 公司官网、产品手册、客户认证、招投标文件
- 调研纪要、业绩说明会、电话会纪要
- 行业报告、券商报告、第三方数据库
- 新闻报道、媒体采访、市场传闻
- 自建数据表、计算结果、估值表

注意：不是所有 evidence 可信度相同。

---

## 3. 来源等级

| 等级 | 来源 | 使用方式 |
|---|---|---|
| A | 交易所公告、公司定期报告、监管文件、正式披露 | 可作为核心事实依据 |
| B | 政策文件、官方统计、行业协会、招投标、中标公告 | 可作为重要背景或行业证据 |
| C | 公司官网、业绩会、投资者关系、调研纪要、第三方数据库 | 可使用，但需标明口径与限制 |
| D | 新闻、社交媒体、市场传闻、未经核验的第三方观点 | 只能作为线索，不可单独支撑关键结论 |

---

## 4. evidence_id 规则

推荐格式：

```text
<source_type>_<entity_or_publisher>_<date_or_period>_<short_hash>
```

示例：

```text
annual_report_300xxx_2025_a1b2c3
announcement_600xxx_2026-03-18_d4e5f6
policy_miit_2026-01-10_a9b8c7
industry_report_xyz_2026Q1_112233
transcript_300xxx_2026-05-09_445566
```

规则：

- `evidence_id` 一经使用，不应随意改名。
- 文件路径变化时，manifest 中更新路径，但尽量保持 ID 稳定。
- 同一资料重复导入时，通过 hash 识别重复。
- 不确定来源时，先标记 `source_type: other`，不要编造来源类型。

---

## 5. Evidence manifest 最小字段

```yaml
evidence_id:
source_type:
source_name:
source_url_or_path:
title:
publisher:
publish_date:
ingested_at:
file_hash:
raw_file_path:
processed_text_path:
reliability_rank: A | B | C | D
license_note:
status: fresh | stale | superseded | contradicted | low_confidence
related_entities: []
notes:
```

---

## 6. 原始证据保存规则

### 6.1 必须保留原始文件

原始文件放：

```text
data/raw/
```

不得覆盖，不得直接编辑。

### 6.2 加工产物另存

加工产物放：

```text
data/processed/text/
data/processed/tables/
data/processed/normalized/
```

### 6.3 证据登记

每个原始证据都应登记到：

```text
data/manifests/evidence_manifest.*
```

P0 阶段可以先用 CSV / YAML / Markdown 表，P1 后再考虑 DuckDB。

---

## 7. Claim 引用规则

关键报告不应只引用整份资料。尽量将核心事实拆成 claim。

### 7.1 Claim 最小字段

```yaml
claim_id:
evidence_id:
entity_type:
entity_id:
claim_text:
claim_type: fact | estimate | inference | management_comment | analyst_view | opinion | unknown
quote_or_excerpt:
page_no:
confidence: high | medium | low
created_at:
valid_until:
status: fresh | stale | superseded | contradicted | low_confidence
```

### 7.2 引用格式

报告中推荐使用：

```text
结论文字。证据：evidence_id=<id>; claim_id=<id>; confidence=<high|medium|low>
```

表格中推荐使用：

| 结论 | 证据 | claim_type | confidence | 备注 |
|---|---|---|---|---|
| 示例结论 | `evidence_id`, `claim_id` | fact | high | 页码或摘录 |

---

## 8. Material claim 定义

Material claim 指可能影响研究判断、评分、watchlist 或投资假设的结论。包括：

- 市场空间、增速、渗透率
- 收入占比、利润贡献、毛利率、订单、产能
- 客户关系、供应链、竞争格局
- 技术壁垒、成本曲线、价格趋势
- 估值假设、业绩弹性、催化剂
- 风险、反证、被证伪的假设
- 公司与细分之间的 exposure_score

Material claim 必须有证据或显式 TODO。

---

## 9. 证据状态

| 状态 | 含义 | 处理方式 |
|---|---|---|
| `fresh` | 当前仍可使用 | 可引用 |
| `stale` | 可能过期 | 可引用但必须标记 |
| `superseded` | 已被新证据覆盖 | 不应作为主证据 |
| `contradicted` | 被新证据反驳 | 必须在反证或更新日志中说明 |
| `low_confidence` | 来源或口径较弱 | 不得单独支撑关键结论 |

---

## 10. 证据新鲜度规则

默认新鲜度建议：

| 证据类型 | 默认有效期 | 说明 |
|---|---:|---|
| 定期报告 | 到下一期报告披露前 | 财报季后应刷新 |
| 临时公告 | 视事项而定 | 并购、订单、募投需跟踪后续进展 |
| 政策文件 | 到政策修订或实施细则变化前 | 注意地方政策差异 |
| 行业报告 | 6-12 个月 | 高景气赛道可能更短 |
| 调研纪要 | 1-3 个月 | 管理层表述变化快 |
| 新闻报道 | 1-4 周 | 只作线索，需核验 |
| 市场价格/估值 | 交易日级别 | 不在 P0 实时维护 |

---

## 11. 冲突证据处理

当证据冲突时，不要只保留一种说法。

必须输出：

```text
冲突点
证据 A
证据 B
来源等级
口径差异
时间差异
哪个结论更稳健
剩余不确定性
下一步核验任务
```

---

## 12. 报告引用要求

每份报告至少包含：

1. `evidence_snapshot`
2. `key_claims`
3. `evidence_map`
4. `missing_data`
5. `counter_evidence`
6. `refresh_status`

---

## 13. 禁止事项

- 禁止编造 `evidence_id`。
- 禁止把无来源数字写成事实。
- 禁止把券商预测写成公司披露。
- 禁止把管理层展望写成已经实现的业绩。
- 禁止只引用新闻支撑关键财务结论。
- 禁止在更新时删除旧证据状态。
- 禁止静默改写历史报告结论。
