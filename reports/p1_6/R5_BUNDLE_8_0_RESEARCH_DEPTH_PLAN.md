# R5 Bundle 8 — Research Depth 基础设施与执行计划

- Bundle：`R5_BUNDLE_8_RESEARCH_DEPTH`
- 基线提交：`6513350ab371cd2e5612fe2fb4a3f4c1f2f5f9d0`
- 日期：`2026-07-12`
- 模块范围：`M3 证据覆盖与研究输入` + `M4 研究分析引擎`
- 当前 workflow：`wf_20260703_stock_first_002837_invic`
- 入口状态：`needs_fix → T2_evidence_acquire_parse → evidence-ingest`

## 1. 为什么现在进入 Bundle 8

Bundle 7 已完成质量基准重置和质量问题回流。当前 Reader 的自动结果为：

```text
score: 59 / 100
quality_band: research_draft
decision: rejected
truthfulness: pass
candidate_blockers: 12
required_next_skill: evidence-ingest
```

Bundle 8 只处理其中四类 M3/M4 问题：

1. 独立底层研究来源不足；
2. 独立行业证据缺失；
3. 同业经营证据不足；
4. 完整分析单元不足。

预测、估值、技术、情绪、事件、Writer 和端到端样例对标继续后置，避免重新把不同问题耦合在同一补丁中。

## 2. 本补丁交付的能力

### 2.1 Evidence Coverage Matrix

新增 source catalog、coverage matrix 和三类 source-only handoff pack 的契约与构建器：

```text
R5_bundle8_evidence_source_catalog.yaml
    ↓
evidence_coverage_matrix.yaml
    ├─ industry_evidence_pack.yaml
    ├─ peer_operating_pack.yaml
    └─ company_operating_evidence_pack.yaml
```

核心规则：

- 只接受 `reviewed / promoted / accepted` 的来源；
- 以 `underlying_source_id` 去重，多个摘录不能冒充多个独立来源；
- 发行人自己的行业描述不能满足独立行业来源门槛；
- 过期、未来日期、未审查来源不进入覆盖计数；
- 同业门槛按独立 peer entity 计算，不按文件数量计算；
- source-only pack 不新增叙事结论，也不推断缺失事实；
- coverage matrix 必须可从 source catalog 原样重建，手工修改汇总数字会失败。

### 2.2 Analysis Pack v2

新增由分析师填写、程序校验的闭环分析单元：

```text
judgment
→ trend
→ causal_mechanism
→ financial_impact
→ supporting sources / metrics
→ counter evidence
→ falsification condition
→ watch metrics
```

必须覆盖七个章节：

```text
core_thesis
financial_quality
business_driver
segment_economics
industry_context
competitive_position
risk_counterevidence
```

程序只验证和拆分分析，不从事实列表自动“写出”结论。它会拒绝：

- 空字段或过短文本；
- 模板化空话；
- 相同判断在多个章节重复；
- 未知、未审查、过期或未进入覆盖矩阵的来源；
- 没有反证、失效条件或量化观察指标的单元；
- 依赖关系不存在、自引用或循环；
- 手工把 blocked 单元改成 complete；
- 不能由原始 inputs 重建的 analysis pack。

通过后确定性拆出：

```text
thesis_tree.yaml
business_driver_tree.yaml
segment_economics.yaml
competitive_position_matrix.yaml
risk_counterevidence_pack.yaml
```

## 3. 门槛

### 证据门

| 项目 | 最低要求 |
|---|---:|
| 覆盖要求 | 7 / 7 |
| 独立底层来源 | 4 |
| 全部底层来源 | 7 |
| 行业需求独立来源 | 2 |
| 行业供给/竞争独立来源 | 2 |
| 有经营数据的独立同业 | 3 |
| 反向证据 | 核心要求均需满足 |

### 分析门

| 项目 | 最低要求 |
|---|---:|
| 完整分析单元 | 7 |
| 必需章节 | 7 / 7 |
| 每单元支持来源 | 1 |
| 每单元反证来源 | 1 |
| 每单元观察指标 | 1 |
| 行业、竞争、风险章节 | 必须含独立来源 |
| 财务、业务驱动、分业务经济性 | 必须含发行人来源 |

门槛是最低闭环，不是样例质量的充分条件。后续人工研究仍需增加公司特异性、量化密度和反向论证。

## 4. 执行顺序

```text
B8-M3-EVIDENCE-COVERAGE
    ↓
B8-M3-INDUSTRY-RESEARCH
    ↓
B8-M4-ANALYSIS-ENGINE
    ↓
B8-INTEGRATION-GATE
```

具体 workstream、来源 blocker 和退出条件已写入：

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/
  R5_bundle8_research_depth_execution_plan.yaml
  R5_bundle8_research_depth_execution_plan.md
```

## 5. 状态边界

本补丁不会：

- 修改 `workflow_state.yaml`；
- 关闭或解决现有 TODO；
- 更新 canonical index；
- 重新生成 Reader；
- 修改 Writer；
- 自动宣布 Bundle 8 closed；
- 自动进入 P2。

只有在真实审查证据上通过 M3/M4 gate、全仓库测试与 CI 通过、truthfulness/no-advice 边界仍为绿色后，才应另建 close-only patch 同步 canonical 状态，并把工作交给 Bundle 9。
