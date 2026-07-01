# Workspace Structure — 目录结构与文件归位规则

## 1. 总原则

本项目采用“证据、配置、模板、报告、决策”分离的结构。

```text
证据是原始输入。
配置定义对象和口径。
模板定义输出形态。
报告是可再生产物。
决策记录保存研究判断变化。
```

不要把原始证据、加工文本、报告、备忘录、配置文件混放。

---

## 2. 根目录

```text
AGENTS.md
README.md
docs/
config/
data/
reports/
templates/
decisions/
tests/
pyproject.toml
.env.example
.gitignore
```

| 文件 | 用途 |
|---|---|
| `AGENTS.md` | Codex 长期规则 |
| `README.md` | 项目说明入口 |
| `docs/` | 项目文档、架构、政策、手册、计划和元索引 |
| `config/` | 研究配置、分类、来源、指标和评分规则 |
| `data/` | 原始证据、加工数据、数据库和 manifest |
| `reports/` | 派生研究报告、比较、刷新和备忘录 |
| `templates/` | 报告、证据卡、比较矩阵和 memo 模板 |
| `decisions/` | thesis log、watchlist 变更和复盘 |
| `tests/` | 工作区验收和回归检查 |

---

## 3. 文档目录 `docs/`

```text
docs/
├── index.md
├── project/
├── architecture/
├── policies/
├── playbooks/
├── plans/
├── logs/
└── meta/
```

### 3.1 计划目录 `docs/plans/`

计划、计划模板和验收清单统一放在 `docs/plans/`，文件名使用英文小写 `snake_case`。

```text
docs/plans/
├── plan_template.md
├── p0_acceptance_checklist.md
├── p0_execution_plan.md
├── p1_execution_plan.md
└── p1_1_revision_plan.md
```

### 3.2 日志目录 `docs/logs/`

计划完成情况、阶段验收记录、closeout 和复盘记录统一放在 `docs/logs/`，不要与计划文件混放。

```text
docs/logs/
├── README.md
├── YYYY-MM-DD_<scope>_<log_type>.md
└── p0/
    ├── YYYY-MM-DD_p0_preplanning_confirmation.md
    ├── YYYY-MM-DD_p0_smoke_test.md
    └── YYYY-MM-DD_p0_closeout.md
```

日志命名规则以 `docs/logs/README.md` 为准；新增日志统一使用 `YYYY-MM-DD_<scope>_<log_type>.md`。

---

## 4. 配置目录 `config/`

```text
config/
├── research_config.yaml
├── segment_taxonomy.yaml
├── source_registry.yaml
├── metric_definitions.yaml
├── scoring_frameworks.yaml
└── watchlist.yaml
```

| 文件 | 用途 |
|---|---|
| `research_config.yaml` | 项目级默认设置、语言、日期、路径、版本 |
| `segment_taxonomy.yaml` | 细分定义、边界、别名、相邻细分 |
| `source_registry.yaml` | 证据来源清单、优先级、可信度、更新频率 |
| `metric_definitions.yaml` | 指标定义、口径、单位、计算方法 |
| `scoring_frameworks.yaml` | 细分和个股评分维度 |
| `watchlist.yaml` | 重点跟踪的细分、个股、指标和催化剂 |

规则：

- 配置文件只放结构化规则，不放长篇分析。
- 新增评分维度必须同步更新模板和质量检查。
- 新增细分必须有 `segment_id`、定义、`scope_in`、`scope_out`。

---

## 5. 证据目录 `data/`

```text
data/
├── raw/
│   ├── announcements/
│   ├── annual_reports/
│   ├── industry_reports/
│   ├── transcripts/
│   └── market_data/
├── processed/
│   ├── text/
│   ├── tables/
│   ├── embeddings/
│   └── normalized/
├── db/
└── manifests/
```

### 5.1 `data/raw/`

原始证据，只新增不覆盖。

| 子目录 | 内容 |
|---|---|
| `announcements/` | 公告、交易所披露、临时公告 |
| `annual_reports/` | 年报、半年报、季报 |
| `industry_reports/` | 行业报告、政策文件、第三方研究 |
| `transcripts/` | 调研纪要、电话会、业绩说明会、访谈 |
| `market_data/` | 结构化行情、财务、行业数据原始导出 |

### 5.2 `data/processed/`

加工产物，可重建。

| 子目录 | 内容 |
|---|---|
| `text/` | PDF/网页/公告解析后的文本 |
| `tables/` | 表格抽取结果 |
| `embeddings/` | 向量索引或嵌入文件 |
| `normalized/` | 标准化后的 CSV/Parquet/YAML |

### 5.3 `data/db/`

本地数据库或索引。

```text
data/db/research.duckdb
data/db/vector.index
```

P0 可以只保留目录，不必实现数据库。

### 5.4 `data/manifests/`

证据和刷新日志的 manifest。

```text
data/manifests/evidence_manifest.*
data/manifests/refresh_log.*
```

---

## 6. Skills 目录 `.agents/skills/`

```text
.agents/skills/
├── evidence-ingest/
├── segment-research/
├── company-universe/
├── segment-company-mapping/
├── stock-deep-dive/
├── compare-segments/
├── compare-stocks/
├── refresh-research/
├── quality-review/
└── memo-writer/
```

每个 skill 目录推荐结构：

```text
<skill-name>/
├── SKILL.md
├── scripts/
├── references/
└── assets/
```

P0 只要求有 `SKILL.md` 空壳和边界说明。

---

## 7. 模板目录 `templates/`

```text
templates/
├── segment_report.md
├── stock_report.md
├── evidence_card.md
├── comparison_matrix.md
├── investment_memo.md
└── refresh_log.md
```

模板必须要求填写：

- metadata
- evidence snapshot
- key claims
- confidence
- risks and counter-evidence
- TODO / missing data
- refresh status

---

## 8. 报告目录 `reports/`

```text
reports/
├── segments/
├── stocks/
├── comparisons/
├── refresh/
└── memos/
```

### 8.1 细分报告

```text
reports/segments/<segment_id>/
├── <date>_segment_report.md
├── company_universe.csv
├── scorecard.yaml
├── evidence_map.md
└── refresh_tasks.yaml
```

### 8.2 个股报告

```text
reports/stocks/<stock_code>_<company_slug>/
├── <date>_stock_deep_dive.md
├── segment_exposure.yaml
├── valuation_scenarios.*
└── evidence_map.md
```

### 8.3 对比报告

```text
reports/comparisons/
├── <date>_segment_comparison.md
├── <date>_segment_score_matrix.csv
├── <date>_stock_comparison.md
└── <date>_stock_score_matrix.csv
```

### 8.4 刷新报告

```text
reports/refresh/
├── <date>_refresh_log.md
├── stale_claims.csv
├── updated_scorecards.yaml
└── reports_to_regenerate.yaml
```

---

## 9. 决策目录 `decisions/`

```text
decisions/
├── thesis_log.md
├── watchlist_changes.md
└── postmortems/
```

规则：

- 研究结论变成观察假设时，写入 `thesis_log.md`。
- watchlist 纳入、剔除、降级、升级，都写入 `watchlist_changes.md`。
- 重大判断错误、错过机会、证据失效，写入 `postmortems/`。

---

## 10. 命名规范

| 对象 | 规则 | 示例 |
|---|---|---|
| `segment_id` | 英文 lower_snake_case | `ai_server_liquid_cooling` |
| 公司目录 | 股票代码 + 公司简称拼音/英文 slug | `300xxx_company_name` |
| 报告文件 | `YYYY-MM-DD_<type>.md` | `2026-06-30_segment_report.md` |
| evidence_id | 来源类型 + 对象 + 日期 + hash | `annual_report_300xxx_2025_a1b2c3` |
| claim_id | claim + 对象 + 主题 + hash | `claim_300xxx_revenue_mix_d4e5f6` |

---

## 11. 禁止事项

- 不在根目录随意创建临时报告。
- 不把 raw evidence 放进 reports。
- 不把报告草稿放进 config。
- 不覆盖 `data/raw/` 文件。
- 不把没有证据的结论写成事实。
- 不把一次性聊天结果当作长期研究状态。
