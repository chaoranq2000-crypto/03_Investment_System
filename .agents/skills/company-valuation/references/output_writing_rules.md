# Valuation Output Writing Rules

## 1. Writing goal

The valuation section should answer:

```text
1. 当前市场如何给这家公司定价？
2. 这些定价口径是否可比、是否过期、是否受周期扰动？
3. 如果使用预测假设，哪些变量最敏感？
4. 同业对比中公司处于什么位置？
5. 哪些证据缺口或反证可能推翻估值判断？
```

It should not answer:

```text
现在该不该买？
仓位应该多少？
目标价是多少？
多久能涨到哪里？
```

## 2. Required section structure

```markdown
## 五、估值分析

### 5.1 静态估值
- 描述 PE TTM / PB / PS / EV/EBITDA 等静态口径。
- 写清 as_of_date、period、数据来源和异常项。
- 不把静态低/高估写成操作结论。

### 5.2 动态估值
- 基于 2026E / 2027E / 2028E forecast_model。
- 写清预测属于 estimate / inference / analyst_view。
- 如果预测缺口大，直接写 TODO，不写确定性数字。

### 5.3 同业估值对比
- 解释可比公司为什么可比，也解释哪里不可比。
- 使用 median，或说明使用 mean 的原因。
- 对极端值和业务差异做 limitation。

### 5.4 情景估值与敏感性
- 使用 bear / base / bull。
- 说明最敏感变量：收入增速、毛利率、净利率、估值倍数、折现率、商品价格等。
- 输出区间和变量影响，不输出交易动作。

### 5.5 估值分歧、反证与后续验证
- 列出哪些证据会让估值判断失效。
- 列出下一步需要补充的数据。
```

## 3. Labeling rules

Use labels inline when needed:

```text
事实：fact
估计：estimate
推断：inference
管理层表述：management_comment
券商或第三方观点：analyst_view
观点性判断：opinion
未知或缺口：unknown / TODO / MISSING
```

## 4. Allowed language

Allowed:

```text
估值处于同业中位数上方/附近/下方
当前估值对某变量敏感
该情景依赖若干估计假设
可比公司口径存在限制
需要后续验证
若关键假设不成立，则估值情景需要下修/重估
```

## 5. Prohibited language

Do not write:

```text
买入
卖出
持有
推荐
强烈推荐
目标价
上车
加仓
减仓
满仓
止盈
止损
必然修复
确定上涨
无风险套利
```

If legacy examples contain these terms, do not copy them into new outputs.

## 6. Evidence and model citation

Every material valuation statement should cite one of:

```text
evidence_id
claim_id
metric_id
source_path
valuation_model.yaml path
peer_comparison.csv path
sensitivity_table.csv path
explicit TODO / MISSING reason
```

Example:

```text
公司 2026E PE 低于可比公司中位数，但该结论依赖 2026E 归母净利润预测，属于 estimate；证据：metric_id=np_2026E_base；模型：valuation_model.yaml#dynamic_valuation。
```

## 7. Report boundary statement

The valuation section should end or footnote with:

```text
本节为估值情景与研究假设整理，不构成任何买入、卖出、持有或其他交易建议。
```
