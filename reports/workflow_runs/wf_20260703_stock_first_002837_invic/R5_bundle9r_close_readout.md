# R5 Bundle 9R 预测与估值前向重建关闭读数

## 关闭结论

- 决定：`accepted_with_todos`
- workflow：`wf_20260703_stock_first_002837_invic`
- 输入证据代际：`evidence_gen_r5_bundle8r_231a51f4673156df`
- 模型代际：`model_gen_r5_bundle9r_1cd42241e6a38fb3`
- 模型 aggregate SHA256：`1cd42241e6a38fb3fc24e6ceb5be1261dbad6e1ee860393b44932282bacd54cc`
- quality gate：`pass`，critical=`0`，high=`0`
- Bundle 10R：`allowed_but_not_started`
- sample-quality：`false`
- P2：`false`

## 代际纠偏

补丁原始 Bundle 8R 锁在声明基线提交中记录了 `claims_draft.csv` 的中间态哈希，无法通过自身要求的锁定输入复核。原锁保持原位作为历史对象；新增 `R5_bundle8r_evidence_generation_lock_v2.yaml` 和 `R5_bundle8r_generation_lock_correction.yaml`。纠偏只重建哈希锁，没有改动证据文件或 `data/raw/`。

## 9R.0—9R.8 执行结果

| 阶段 | 状态 | 可审计结果 |
|---|---|---|
| 9R.0 baseline / generation binding | pass | 6 个锁定输入哈希全部一致；当前代际与 binding 一致；workflow 先预览后写入。 |
| 9R.1 input review | accepted_with_explicit_gaps | 2025A 与 2026Q1 收入、归母净利润已和发行人报告直接披露值核对；45 条预测假设含 claim type、证据/指标、置信度、失效条件和 reviewer decision。 |
| 9R.2 segment driver model | pass_with_todo | room cooling、cabinet cooling、other businesses 覆盖 3 情景 × 3 年；液冷仅保留不加总的未量化分析视图并关联披露缺口。 |
| 9R.3 statement bridge | pass | 从分部毛利到归母利润、EPS、经营现金流、capex、自由现金流完整勾稽；原汇总残差被 6 个显式报表科目替换。 |
| 9R.4 scenarios / sensitivity | pass | 收入和归母利润满足 bear <= base <= bull；12 条单变量、9 条双变量敏感性。 |
| 9R.5 peer / consensus | accepted_with_todos | 外部 EPS 分布为 10—12 家机构且仅作 `analyst_view`；四家同业维持 `LOW_CONFIDENCE_PEER_SET`、禁止排名。 |
| 9R.6 valuation | pass_with_todos | 总市值与收盘价×股本相对差异 `0.00006752%`；反向估值和三情景估值可用；DCF、SOTP 未满足方法门。 |
| 9R.7 quality / negative tests | pass | 正向 fixture 通过；stale ID、输入哈希漂移、液冷事实越界/重复加总、缺分部/桥科目、禁用残差、算术/单调性/市值错误、低置信度排名、缺估值方法、consensus 误标和动作语言均 fail-closed。 |
| 9R.8 close / model lock | pass | 13 个核心模型产物写入哈希锁，缺失数 0；连续两次重建 12 个生成产物，哈希变化数 0；CSV 固定 LF，提交规范化不会改变锁定字节。 |

## 验证记录

- 代际绑定：`decision=pass`，issues=`0`。
- 模型质量门：`decision=pass`，critical=`0`，high=`0`。
- 9R 聚焦及历史关闭态兼容回归：`38 passed`。
- 全仓库回归：`674 passed, 2 skipped in 28.56s`。
- 禁用动作语言扫描：当前 9R 产物无命中。
- 历史边界：旧 Bundle 9、旧 Bundle 10 及现有 `bundle10r/` 未删除、未覆盖；旧 Reader 对新模型代际标记为 stale。

## 保留 TODO

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `R5B9R-DISC-001` | medium | evidence-ingest | 出现同口径发行人披露后刷新独立液冷经济性与消除关系。 |
| `R5B9R-DRIVER-001` | medium | stock-deep-dive | 补齐项目/容量/单价/验收节奏到收入的可审阅转换证据。 |
| `R5B9R-PEER-001` | medium | company-valuation | 补齐同业官方经营口径前继续禁止排名。 |
| `R5B9R-DCF-001` | medium | company-valuation | 净债务、折现率和终值假设全部可追溯后重新检查 DCF 资格。 |
| `R5B9R-SOTP-001` | medium | company-valuation | 独立分部经济性、未分配成本与消除关系可审阅后重新检查 SOTP 资格。 |

## 边界

本关闭只完成最新 Bundle 9R 计划，不生成 Reader、不启动 Bundle 10R、不进入 P2，也不恢复 sample-quality 许可。后续若有明确计划，Bundle 10R 只能消费 `R5_bundle9r_model_generation_lock.yaml` 所绑定的精确模型代际。
