# R5 Bundle 7.0 — Reader Quality Rebaseline 与 Workflow Backflow 计划

status: `proposed_patch`
base_commit: `a7a193203145042745dc66522fe22332da2026d7`
as_of_date: `2026-07-12`
scope: `M1 Reader Quality Gate + M2 canonical workflow fix-loop`

## 一、目标

本任务只处理重构计划的第一步：先让低质量报告被正确判低质量，再让失败结果回流到正确责任模块。它不在本 Bundle 内补行业证据、不重建分业务预测、不重写 Writer，也不直接修改全局 canonical index。

目标状态：

```text
Reader report
    ↓
positive-from-zero quality gate
    ├─ truthfulness blockers → fail closed
    └─ research-depth blockers → deterministic fix routes
                                     ↓
                          workflow_state / TODO / manifest
                                     ↓
                     evidence → analysis → forecast → valuation
```

## 二、基线问题

Bundle 6 的质量门先复制满分维度，再仅因格式、引用、算术或泄漏问题扣分，导致“标题齐全、引用可解析、没有内部字段”被误判为 100 分。当前报告仍缺少独立行业证据、可信同业经营对比、分业务驱动预测、反向估值、技术/情绪输入和完整未来事件链，因此不能进入 reader candidate 状态。

同时，Bundle 6 close readout、workflow state、workflow readout、open TODO 与 artifact manifest 没有形成一个同步的当前状态面。质量失败后系统也没有明确返回 evidence-ingest 或下游责任模块。

## 三、本补丁内容

### M1：正向质量评分

1. 评分从 0 开始，不再默认填入满分。
2. 将 truthfulness blocker 与 candidate blocker 分离：
   - truthfulness blocker 表示引用、内部字段、算术、虚构人审等硬错误；
   - candidate blocker 表示证据覆盖、分析闭环、预测、估值、市场事件等研究深度不足。
3. 把报告第八节“有日期的公司事件”纳入必需章节。
4. 对每节生成诊断：汉字数、数字事实数、段落数、引用数、分析信号、密度和分析单元是否闭合。
5. 候选报告必须同时满足：
   - 总分至少 82；
   - truthfulness blocker 为 0；
   - candidate blocker 为 0；
   - 至少 7 个核心章节完成“判断—趋势—因果—经济影响—反证—观察点”所需信号；
   - 总正文至少 3,200 个汉字；
   - 至少 2 个独立底层来源；
   - 至少 3 个可信同业上下文；
   - 预测、估值、技术、情绪和未来事件具备最低能力。
6. 输出四种质量带：
   - `blocked`
   - `source_gapped_draft`
   - `research_draft`
   - `candidate_ready_for_human_review`
7. 质量门输出按问题类型聚合的 `fix_routes`。

### M2：确定性状态回流

新增 `reconcile_r5_quality_backflow.py`：

1. 默认 dry-run，不修改仓库状态。
2. 从 v0.2 scorecard 生成确定性 backflow plan 和 readout。
3. 失败时按优先级路由：
   - `T2_evidence_acquire_parse / evidence-ingest`
   - `T5_analysis_pack_build / stock-deep-dive or segment-research`
   - `T6_forecast_valuation_model / stock-deep-dive`
   - `RP6_valuation / company-valuation`
   - `T7_technical_sentiment_event_pack / stock-deep-dive`
   - `T8_report_draft / memo-writer`
4. `--apply` 时同步：
   - `workflow_state.yaml`
   - `open_todos.csv`
   - `artifact_manifest.csv`
   - `workflow_readout.md`
5. 历史通过状态保留用于审计，但标记为被 Bundle 7 rebaseline supersede，不再作为当前状态。
6. 生成稳定的 `R5Q-B7-*` issue ID；重复执行不会重复写入 TODO 或 artifact。
7. 不自动修改 `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md`。只有完整测试、truthfulness 检查和人工审阅补丁差异后，才能由单独 close task 晋升 canonical readout。

## 四、当前基线的预期结果

使用最新 Bundle 6 Reader v2、traceability appendix、forecast bridge 和 valuation pack：

```text
decision: rejected
quality_band: research_draft
score: 59 / 82
truthfulness_status: pass
candidate_blockers: 12
human_review_status: not_ready
first_fix_route: T2_evidence_acquire_parse / evidence-ingest
```

这不是回归失败，而是本补丁的核心验收结果：报告在真实性与展示卫生上合格，但研究深度不足，因此应返回补证据和分析，而不是进入人工候选。

## 五、验收标准

### 必须通过

- 当前 Reader v2 得分位于 40–60，并被判为 `research_draft`。
- “10 个标题 + 10 句空话”直接失败，触发极薄报告和分析单元不足。
- 一个具备完整证据、分业务预测、反向估值、技术/情绪和事件链的合成样本能够真正通过。
- 原有引用、内部路径、TODO、算术、估值日期、交易建议、虚构人审等负向测试继续 fail closed。
- backflow dry-run 将第一个修复环节指向 evidence-ingest。
- backflow apply 同步四个状态文件，且重复执行幂等。
- 完整仓库测试、truthfulness gate 和 `git diff --check` 通过。

### 明确不在本 Bundle 验收范围

- 新行业证据是否已经采集；
- 分业务预测是否已经重建；
- Writer 是否已经去硬编码；
- Reader v3 是否达到样例质量；
- P2 是否可进入。

这些属于 Bundle 8–10。

## 六、风险与边界

- 来源分类目前基于底层 evidence ID 的命名启发式，是 M1 的防假阳性措施，不替代 M3 的正式 evidence taxonomy。
- 章节“分析信号”由正则检测，仍可能被堆词绕过；本补丁通过来源多样性、预测对象、估值对象和市场事件对象共同降低该风险，真正的语义闭环验证应在 M4 完成。
- 3,200 字和章节最小密度是候选门槛，不是鼓励灌水；没有独立证据或底层模型时，增加文字不会消除 blocker。
- 当前 59 分只绑定最新 Bundle 6 工件；报告或上游工件变化后必须重新运行。

## 七、下一 Bundle 的入口条件

本补丁合并后，Bundle 8 才能开始 M3 + M4：

```text
evidence_coverage_matrix
industry_evidence_pack
peer_operating_pack
company_operating_evidence_pack
        ↓
thesis_tree
business_driver_tree
segment_economics
competitive_position_matrix
risk_counterevidence_pack
```

Bundle 8 的输入应直接使用本补丁生成的 `fix_routes` 与 `R5Q-B7-*` TODO，而不是另起一套缺口清单。

## 八、执行期兼容校正

- 全仓验证发现 Bundle 6 close 工件记录的 Reader v2 报告 SHA256 与同一基线提交中的实际 Git blob 不一致；已将人审 handoff 与 close readout 中的绑定值从 `096e28c7a3ed686dbdcade76c3e200d2f7130144fd668660463c3c5b83a7aaa3` 校正为 `54ec29f5e1bb6302cc63bd3cfc2ae91dcf60ac2a4754918a15c308b1aae96309`。报告正文未修改。
- Bundle 6 close token 继续作为历史快照保留；当前决策面改由 Bundle 7 v0.2 scorecard 提供，其状态为 `rejected / research_draft / 59`。
- 旧合同测试已同步到 v0.2 的 10 节结构与 `human_review_required` 字段；未放宽 truthfulness、no-advice、人审或 P2 边界。
- GitHub Actions 暴露出 Bundle 6 baseline 对 YAML 工作区行尾字节的跨平台绑定；已将该文本哈希校正为 Git blob 对应的 canonical LF UTF-8 SHA256 `f8d7fbcda0dc5cc5a783e7994935e2434c872da60119af9b41e921ddac54d3bf`，并增加 CRLF/LF 等价测试。工件语义内容未修改。
