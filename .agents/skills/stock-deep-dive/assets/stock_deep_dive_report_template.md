# 价值发现：{{stock_name}}

## 0. Metadata

| 字段 | 内容 |
|---|---|
| stock_code | {{stock_code}} |
| company_id | {{company_id}} |
| report_date | {{report_date}} |
| quality_target | {{quality_target}} |
| evidence_snapshot | {{evidence_snapshot}} |
| report_status | draft / accepted_with_todos / accepted_sample_quality |

## 前言

{{opening_thesis}}

## 一、财务概览

### 1.1 财务报表

{{income_statement_narrative}}

| 期间 | 营收 | 归母净利 | 扣非净利 | 毛利率 | 净利率 | 证据 |
|---|---:|---:|---:|---:|---:|---|
| {{period}} | {{revenue}} | {{np}} | {{deducted_np}} | {{gm}} | {{nm}} | {{metric_ids}} |

### 1.2 财务指标与质量

{{financial_quality_narrative}}

## 二、业务拆分

{{business_summary}}

| 业务 | 收入 | 占比 | 毛利率 | 毛利贡献 | 增长驱动 | 证据 | 置信度 |
|---|---:|---:|---:|---:|---|---|---|
{{business_table_rows}}

### 2.1 {{business_line_1}}

{{business_line_1_narrative}}

### 2.2 {{business_line_2}}

{{business_line_2_narrative}}

## 三、行业分析

{{industry_intro}}

### 3.1 {{segment_1}}

{{segment_1_narrative}}

### 3.2 公司在价值链中的位置

{{value_chain_position}}

## 四、盈利预测

{{forecast_intro}}

| 指标 | 2026E | 2027E | 2028E | 核心假设 | 证据/模型 |
|---|---:|---:|---:|---|---|
{{forecast_table_rows}}

{{forecast_sensitivity_narrative}}

## 五、估值分析

### 5.1 静态估值

{{static_valuation_narrative}}

### 5.2 动态估值

{{dynamic_valuation_narrative}}

### 5.3 同业对比

| 公司 | 代码 | 业务相关性 | PE TTM | 2026E PE | 2027E PE | 备注 |
|---|---|---|---:|---:|---:|---|
{{peer_table_rows}}

{{valuation_conclusion}}

## 六、技术分析

{{technical_narrative}}

## 七、情绪分析

### 7.1 宏观情绪

{{macro_sentiment}}

### 7.2 行业/主题情绪

{{industry_sentiment}}

### 7.3 公司情绪

{{company_sentiment}}

## 八、事件驱动

| 日期/窗口 | 事件 | 影响变量 | 超预期条件 | 低于预期风险 | 证据 |
|---|---|---|---|---|---|
{{event_table_rows}}

{{event_narrative}}

## 九、研究结论、风险与跟踪清单

{{conclusion_narrative}}

### 风险与反证

{{risk_counter_evidence}}

### 后续跟踪指标

| 指标 | 为什么重要 | 频率 | 来源 | 触发动作 |
|---|---|---|---|---|
{{tracking_table_rows}}

## 附录 A：Evidence Map

| 结论 | claim_id / metric_id | evidence_id | 来源 | 日期 | 页码/表格 | 置信度 |
|---|---|---|---|---|---|---|
{{evidence_map_rows}}

## 附录 B：Open Questions / Evidence Gaps

{{open_questions}}
