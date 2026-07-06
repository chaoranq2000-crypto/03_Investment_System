# Sample Style Guide for Stock Report Writer

## 0. Writer Boundary

Use this guide inside SDD-3 Report drafting. The drafting stage translates
`stock_analysis_pack.yaml` and approved component files into narrative.

It must not:

```text
- Discover facts outside the analysis pack.
- Fill missing business, financial, customer, order, forecast or valuation
  fields with guesses.
- Hide TODO, MISSING, LOW_CONFIDENCE or UNVERIFIED labels.
- Turn valuation, technical or sentiment observations into trading actions.
```

When a needed input is absent, write a visible gap request instead of a smooth
unsupported sentence.

## 1. What to emulate

Emulate these qualities:

```text
- Strong opening thesis.
- Section-level conclusions.
- Business-line narrative, not just tables.
- Industry context tied to company exposure.
- Forecast driven by named variables.
- Valuation framed around market disagreement.
- Technical/sentiment/event sections with dated observations.
- Risks and uncertainties integrated into the conclusion.
```

Do not emulate unsupported buy/sell/position language.

## 2. Preferred narrative pattern

```text
{{conclusion}}。
从数据看，{{metric evidence}}。
背后的核心变量是 {{driver}}。
这意味着 {{investment meaning as research observation}}。
但 {{risk or counter-evidence}} 仍然需要验证。
```

## 3. Heading conventions

```text
价值发现：{{company_name}}
前言
一、财务概览
1.1 财务报表
1.2 财务指标
二、业务拆分
2.1 {{business_line}}
三、行业分析
四、盈利预测
五、估值分析
六、技术分析
七、情绪分析
八、事件驱动
九、研究结论
```

## 4. Evidence-light wording

When evidence is incomplete:

```text
目前证据只能支持“{{weaker_statement}}”，尚不足以证明“{{stronger_statement}}”。
```

Examples:

```text
目前证据只能支持公司已布局液冷相关产品，尚不足以证明液冷业务已贡献可量化收入占比。
```

## 5. Conclusion language

Use:

```text
research_status: high_conviction_watch / watch / neutral_watch / risk_watch
```

Instead of:

```text
buy / sell / hold / 仓位 / 加仓 / 减仓
```
