# A-share Research OS / A股投研工作区

> 这是一个证据驱动的 A 股投研工作区，不是自动交易系统，也不直接提供买卖建议。

## 1. 项目定位

A-share Research OS 的目标是把 A 股投研过程拆成可维护、可复用、可审查的工作流：

```text
用户输入：细分方向 / 股票 / 对比任务 / 更新任务
        ↓
Codex Skills：标准化投研动作
        ↓
研究对象库 + 证据库：沉淀证据、事实、指标、映射关系和状态
        ↓
产出层：细分报告、个股深度、对比矩阵、观察清单、投资备忘录
```

核心思想：

- 证据库是核心。
- 报告是某一时点的可再生产物。
- 细分方向和上市公司是多对多关系。
- 投研结论必须能追溯证据。
- 更新研究时必须输出变化。

---

## 2. 当前阶段

当前处于 **P1.5：pre-P2 hardening / 进入 P2 前加固**。

阶段状态：

- P0：CONDITIONAL_PASS，工作区骨架、规则、skills、配置、模板和最小质量纪律已经建立。
- P1：CONDITIONAL_PASS_WITH_MEDIUM_TODOS，`ai_server_liquid_cooling` 已跑通证据、细分报告、公司池、个股样本、暴露映射和观察清单闭环。
- 当前焦点：修复进入 P2 前的工程门禁、registry、exposure 口径、scorecard 一致性和 CI 验收。

P1.5 只做：

- 保持 P0/P1 已有闭环可运行。
- 把 draft claims/metrics 拆成 draft + registry 两层。
- 强化 evidence manifest、segment-company exposure、quality issues 的字段。
- 增加 P1.5 hardening tests 和 GitHub Actions CI。
- 明确剩余 TODO，不把缺口伪装成已解决。

P1.5 不做：

- 扩展新细分。
- 新增 P2 comparison 报告。
- 批量扩大公司池。
- 自动估值模型。
- 实时行情监控。
- 自动交易。
- 买卖建议生成。

---

## 3. 阶段路线图

| 阶段 | 目标 | 关键词 | 暂停点 |
|---|---|---|---|
| P0 | 搭骨架 | `AGENTS.md`、目录、模板、配置、skills 空壳 | Codex 能理解项目规则和文件位置 |
| P1 | 跑通一个闭环 | 一个细分 → 公司池 → 1-2 个个股 → 评分 → 观察清单 | 关键结论可追溯证据 |
| P2 | 做比较 | 多个细分、多个个股横向比较 | 形成 watchlist 和 research_queue |
| P3 | 做维护 | 新证据驱动旧结论更新 | 输出 refresh log、stale claims、postmortem |

---

## 4. Documentation

文档总入口：[`docs/index.md`](docs/index.md)

| 文件 | 用途 |
|---|---|
| `AGENTS.md` | Codex 项目级长期规则和投研纪律 |
| [`docs/project/PROJECT_CHARTER.md`](docs/project/PROJECT_CHARTER.md) | 项目目标、范围、非目标、路线图和暂停点 |
| [`docs/architecture/WORKSPACE_STRUCTURE.md`](docs/architecture/WORKSPACE_STRUCTURE.md) | 目录结构、文件归位、命名规则 |
| [`docs/policies/QUALITY_GUARDRAILS.md`](docs/policies/QUALITY_GUARDRAILS.md) | 质量检查、反幻觉、反证、风险纪律 |
| [`docs/plans/P0_ACCEPTANCE_CHECKLIST.md`](docs/plans/P0_ACCEPTANCE_CHECKLIST.md) | P0 验收清单 |

---

## 5. 推荐目录结构

```text
a-share-research-os/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
│
├── .codex/
│   └── config.toml
├── .agents/
│   └── skills/
├── docs/
│   ├── index.md
│   ├── project/
│   ├── architecture/
│   ├── policies/
│   ├── playbooks/
│   ├── plans/
│   └── meta/
├── config/
├── data/
│   ├── raw/
│   ├── processed/
│   ├── db/
│   └── manifests/
├── src/
├── notebooks/
├── templates/
├── reports/
├── decisions/
└── tests/
```

---

## 6. Skills 规划

P0 阶段先建立 skills 空壳，后续逐步实现。

| Skill | 投研动作 |
|---|---|
| `evidence-ingest` | 证据导入、归档、解析、登记 |
| `segment-research` | 细分方向研究 |
| `company-universe` | 从细分寻找 A 股公司池 |
| `segment-company-mapping` | 维护细分和公司的多对多暴露关系 |
| `stock-deep-dive` | 个股深度研究 |
| `compare-segments` | 多个细分横向比较 |
| `compare-stocks` | 多个个股横向比较 |
| `refresh-research` | 更新已有研究，输出变化日志 |
| `quality-review` | 证据、口径、反证、过期结论检查 |
| `memo-writer` | 生成投资备忘录、观察清单或 thesis note |

---

## 7. 最小使用方式

### 7.1 细分研究

```text
$segment-research 调研“AI服务器液冷”，深度=standard。
要求：明确细分边界、产业链位置、A股公司池、关键指标、风险与反证，关键结论引用 evidence_id。
```

### 7.2 个股深度

```text
$stock-deep-dive 调研 300xxx，关联细分包括 AI服务器液冷、数据中心电源。
要求：输出业务拆分、细分暴露、财务质量、估值场景、反证清单和 evidence_map。
```

### 7.3 横向比较

```text
$compare-segments 对比 AI服务器液冷、CPO、先进封装、机器人丝杠。
按市场空间、增速、A股纯度、业绩兑现度、估值拥挤度、催化剂和风险排序。
```

### 7.4 更新维护

```text
$refresh-research 更新 watchlist 中的细分和个股。
只输出变化，不要重写所有报告；标记 stale、superseded、contradicted claims。
```

---

## 8. P0 完成标准

P0 完成后，应能回答：

1. Codex 进入项目后是否知道这是 A 股投研工作区？
2. 原始证据应该放在哪里？
3. 处理后的文本和表格应该放在哪里？
4. 细分报告、个股报告、对比报告应该放在哪里？
5. 投资假设、观察清单、复盘应该放在哪里？
6. 一个细分如何命名？
7. 一个公司如何映射到多个细分？
8. 每个 skill 什么时候该用，什么时候不该用？
9. 报告模板是否要求 `evidence_id` 或 `claim_id`？
10. 是否有最小质量检查规则？

只要这些问题可以清楚回答，P0 就应该暂停，进入 P1，而不是继续加复杂功能。
