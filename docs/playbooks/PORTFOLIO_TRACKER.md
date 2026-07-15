# Portfolio Tracker — 本地持仓与交割单操作手册

## 1. 定位与边界

`src/portfolio/` 是一个本地、只做记录和核算的持仓台账：

- 用期初快照建立持仓；
- 按日期记录用户确认的账户现金余额，并保留历次快照；
- 用 Tushare 更新每只证券的最新可得收盘价；
- 按需缓存前复权日 K 线和单日分钟行情，并在所选持仓周期内标注事实型操作点；
- 用券商 CSV/XLSX 交割单更新数量、剩余成本和已实现盈亏；
- 自动识别持仓数量归零的完整清仓周期，并计算清仓收益；
- 保留成交、行情和导入批次，支持去重和历史时点重放；
- 不下单，不生成买入、卖出、持有或仓位建议。

正式数据库只有一份：普通 checkout 使用本工作树的 `data/db/portfolio.sqlite3`；从 linked worktree 运行 CLI 或桌面启动器时，会自动解析到主工作树的同一路径。分支工作树中的 `data/db/portfolio.sqlite3` 是保留路径，即使通过旧命令显式传入也会重定向到主工作树，不能成为第二份正式库。影子验证必须显式使用不同文件名，例如 `--db data/db/portfolio.shadow.sqlite3`。主工作树的 `.env.local` 也按同一规则共享。`data/db/` 下的 SQLite、CSV 和 Excel 文件均被 Git 忽略，个人持仓和交割单不会进入公开仓库。

## 2. 快速开始

以下命令均在仓库根目录执行，并使用项目 conda 环境：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio init
```

复制并填写 `templates/portfolio_opening_snapshot.template.csv` 后导入期初持仓：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio import-opening `
  --input C:\path\to\portfolio_opening.csv
```

抓取最新可得收盘价并查看持仓：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio refresh-prices
.\.conda\investment-system\python.exe -m src.portfolio show
```

记录当前现金余额（来源标记为 `user_provided`，并作为后续交割单现金重放的日终锚点）：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio set-cash `
  --amount 12345.67 `
  --as-of 2026-07-14 `
  --note "用户确认当前现金余额"

.\.conda\investment-system\python.exe -m src.portfolio cash
```

同一天重复记录不会覆盖旧值；页面和历史回看会选择截止日以前最新录入的快照。
普通交割单导入后会从最近一次非 `statement_calculated` 现金锚点开始，重放锚点日之后的全部
`BUY / SELL / DIVIDEND / CASH_FEE`，追加一条 `statement_calculated` 现金快照。用户再次执行
`set-cash` 即建立新的日终锚点，后续只重放更晚日期的成交。总资产按“证券市值 + 现金余额”
展示，证券成本与盈亏口径不受现金快照影响。

更新行业标签：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio refresh-industries
```

行业透视遵循可追溯分类，不做无来源猜测：

- 股票使用 Tushare `stock_basic.industry`，再通过
  `config/portfolio_industry_taxonomy.json` 归一到可合并行业；例如 `化学制药`、`生物医药`统一为
  `医药生物`，原始标签仍保存在 `industry_source`；
- ETF 只读取 `config/portfolio_industry_taxonomy.json` 中经复核的 `ts_code`、跟踪指数和看板行业映射；
- 刷新时若 Tushare `etf_basic` 可用，会核对 `index_code` 和 `index_name`；发生变化即标记
  `未分类（ETF需复核映射）`，不会按 ETF 名称猜测；
- 宽基或跨行业 ETF 需要显式复核为 `跨行业ETF`；未登记 ETF 保持未分类；
- 看板不抓取 ETF 成分、港股行业或成分价格，也不做成分级行业穿透；
- 每只证券保存 `industry_source` 和 `industry_updated_at`；行业标签是当前分类，不随历史回看日重放。

启动本地可视化页面：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio web
```

页面默认在 `http://127.0.0.1:8765/` 打开，提供持仓总览、本月/近几个月/今年/投资以来盈亏曲线、资产占比、盈亏贡献（浮盈前 5 与浮亏前 5）、行业透视、清仓收益、证券筛选与排序、历史时点查看、隐私遮罩和 CSV 导出。“近几个月”默认显示近 3 个月，并可切换近 1、3、6、12、24 个月，最长 2 年；滚动区间选择器始终可见，选择任一时长会自动切换到对应曲线。每个滚动区间都截至当前回看日单独归零计算，选择会保存在当前浏览器。若所选区间早于账户基准日，页面从基准日开始展示可追溯盈亏并明确提示历史不完整，不再把整个区间显示为 `MISSING`。行业透视同时展示按行业市值权重绘制的饼图，保留权重最高的 7 个行业并将其余行业合并为“其他行业”；点击行业行可展开对应持仓证券，并可继续进入单只证券详情。清仓收益按证券聚合为一行，点击后展开该证券的每次完整清仓周期，再点击周期进入操作复盘。资产总览、市值分布、盈亏贡献、行业透视、清仓收益和持仓明细六个模块均可独立折叠，折叠状态保存在当前浏览器。每次打开最新视图时，页面会在后台自动补齐盈亏曲线所需的历史收盘价：首次按各证券实际持有区间抓取，此后只请求尚未覆盖的增量日期；完成后自动重算曲线。历史时点查看不会触发联网更新，自动抓取失败时保留现有曲线并显示待重试提示。最新视图仍会在页面可见时每 60 秒刷新一次盘中行情；页面中的“更新收盘价”和“更新行业”分别保留正式收盘价与行业刷新逻辑。按 `Ctrl+C` 停止服务。

### 盈亏曲线口径

- `本月盈亏` = 回看日投资以来累计盈亏 - 本月开始前最后一个可追溯估值日的累计盈亏；
- `近 N 个月盈亏` = 回看日投资以来累计盈亏 - 回看日前 N 个日历月对应日期前最后一个可追溯估值日的累计盈亏；支持 N = 1、3、6、12、24；
- 若近 N 个月的起点早于账户基准日，则从基准日盈亏归零后展示可追溯区间，同时保留 `partial_history` 和覆盖提示，不伪造基准日前数据；
- `今年盈亏` = 回看日投资以来累计盈亏 - 本年开始前最后一个可追溯估值日的累计盈亏；
- `投资以来盈亏` = 当前持仓浮动盈亏 + 可追溯完整清仓与周期外现金项目的已实现盈亏；
- 曲线只重放本地 `ledger_entries` 与 `close_prices`，不会为缺失行情猜值；无新收盘价的日期沿用最近一次已归档收盘价，行情不完整时返回 `missing_price`，月初或年初早于账户基准日时返回 `partial_history`；
- 自动更新只新增 `close_prices` 并记录各证券已请求的曲线行情覆盖范围，不修改交易流水；同一证券后续打开仅补齐覆盖范围前后的缺口；
- 若导入了基准日前的历史完整清仓流水，其收益统一计入“已实现盈亏”和“投资以来盈亏”。

### 日 K、分时与操作点复盘

点击当前持仓或任一完整清仓周期，会打开宽版详情抽屉：

- 默认读取最近 3 个月的本地缓存，也可切换到最近 1 年或本轮持仓；
- 当前周期截止回看日；清仓周期最多延伸到清仓后 20 个交易日；本轮视图最多带入建仓前 60 个交易日；
- K 线默认显示成交量副图；展开“副图指标”可多选或隐藏技术指标，选择保存在当前浏览器；
- 可选目录覆盖 KLineChart v10 的 27 个内置指标：`VOL / OBV / VR / EMV / PVT / AVP / MACD / DMI / DMA / TRIX / SAR / BBI / KDJ / RSI / WR / BIAS / CCI / MTM / ROC / PSY / AO / MA / EMA / SMA / BOLL / CR / BRAR`；
- 指标由浏览器在同批前复权 `open / high / low / close / volume / turnover` 上按 KLineChart `10.0.0` 默认参数即时派生，不额外访问行情源，也不把派生值写入 SQLite；`EMV` 与 `AVP` 使用同批成交额字段；
- 窗口不足时指标起始段保留为空；指标只用于历史查看，不生成交易信号或直接买卖建议；
- `OPENING` 使用 `total_cost / quantity` 作为“期初成本参考”，不冒充历史买入；
- 同日同方向多笔成交合并为一个操作点，原始流水仍可逐笔展开；同日买入和卖出保持独立；
- 蓝色为买入、琥珀色为卖出、灰色为期初。标注不可拖动，点击后定位到对应流水；
- 点击当前图中任意一根不晚于回看日的日 K（包括建仓前和清仓后的上下文 K 线），会自动切换到“分时”、联网更新该交易日分钟行情并显示结果；若更新失败则回读已有缓存；上下文日期不显示伪造的成交点，买卖点仍只取所选持仓周期；
- 打开详情和切换日 K 区间只访问 SQLite；点击“更新 K 线”、点击日 K、首次切换“分时”进入最近交割单成交日、选择“本轮成交日”或手动选择交割单成交日时，会自动联网更新对应单日分时。普通非成交日仍只读缓存，不会批量刷新整轮成交日。

详情中的“分时”页按单日展示未复权价格面积线、日内累计均价线和独立保存的副图选择：

- 默认日期为所选周期最近一笔 `BUY` / `SELL` 的日期；没有成交时使用 `as_of`；进入该默认成交日、点击“本轮成交日”快捷项或在日期输入中选择交割单成交日会自动更新该日分时，非成交日只读取 SQLite；
- 股票与 ETF 分别优先请求 Tushare `stk_mins` / `etf_mins` 的 1 分钟数据；缺少凭据、权限、返回为空或校验失败时，明确回退 BaoStock 未复权 5 分钟数据；
- 分钟行情校验证券代码、交易日、上海时区、交易时段、OHLC 关系、非负成交量/成交额和重复时间；双源失败不会覆盖已有缓存；
- 日内均价按“累计成交额 ÷ 累计成交量”计算；零成交量分钟沿用上一有效均价，首个有效值之前留空；
- 分时首次加载自动适应全日；1 分钟和 5 分钟分别限制最大柱宽，避免滚轮或触控板过度放大；缩放后可点击“适应全日”恢复完整日内走势；
- 只消费所选 ledger cycle 的 `BUY` / `SELL`。成交映射到同一交易时段内第一个不早于成交时刻的分钟结束桶；1 分钟和 5 分钟精度分别披露；
- 同一分钟同方向成交合并，买卖保持分开，标记纵坐标为未复权的实际成交加权均价；原始成交秒、数量、费用、来源行仍逐笔可展开；
- 无时间、午休/盘外时间或缺少对应分钟条的流水进入“时间未知 / 未定位成交”；不推断时间，`OPENING` 和 `included_in_opening` 观察也不会冒充成交点；
- 手动点击“更新分时”或触发上述成交日自动更新时才联网，页面会显示来源、1/5 分钟频率、更新时间、回退原因以及已定位/未定位数量。

命令行显式更新当前持仓的 K 线：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio refresh-kline `
  --code 600000.SH `
  --range 3m
```

更新指定清仓周期：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio refresh-kline `
  --code 600000.SH `
  --range cycle `
  --cycle-id 600000.SH:1 `
  --as-of 2026-07-14
```

命令行显式更新单日分时缓存：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio refresh-intraday `
  --code 600000.SH `
  --date 2026-07-14 `
  --cycle-id 600000.SH:1 `
  --as-of 2026-07-14
```

股票使用 Tushare `daily + adj_factor`，ETF 使用 `fund_daily + fund_adj`。SQLite 保存原始 OHLCV 与复权因子观察值，读取时按
`原始价 × 当日因子 ÷ 展示截止日锚定因子` 计算前复权价格。任一展示交易日缺少复权因子时，页面会明确标记 `incomplete`，不会用未复权价格替代。

前端源码位于 `src/portfolio/frontend/`，运行时只使用构建后的本地静态文件：

```powershell
Set-Location src\portfolio\frontend
npm install --no-audit --no-fund
npm test
npm run build
```

Vite 已设置 `emptyOutDir: false`，不会自动清空输出目录。不要递归删除 `node_modules` 或构建目录。

盘中行情采用独立的展示层，不写入 SQLite：

```text
腾讯财经批量报价
  → 缺失或失败时使用新浪批量报价
  → 两者都不可用时显示最近 Tushare 正式收盘价
```

- 股票和 ETF 均按当前持仓批量请求；页面显示行情来源、行情时间和覆盖数量。
- 盘中价只用于重新计算页面上的市值、浮动盈亏、收益率、权重、图表和行业汇总，不修改成交、成本或清仓收益。
- 切换到历史回看日后停止盘中覆盖；回到“最新”时恢复。
- 页面隐藏时暂停轮询，重新可见后立即刷新一次；服务端使用 55 秒缓存，避免多个本地标签页重复请求。
- 如果实时源不可用，页面会标注“使用正式收盘价”，持仓账本仍可正常查看。

服务只允许绑定本机回环地址，不会监听局域网或公网。若不希望启动时自动打开浏览器：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio web --no-open
```

Windows 桌面快捷启动使用 `scripts/start_portfolio_dashboard.ps1`。桌面快捷方式可放在 `%USERPROFILE%\Desktop\持仓账本.lnk`：双击后会先检查本地服务；若服务尚未运行，则在后台隐藏启动，健康检查通过后再打开默认浏览器。这个过程不依赖 Codex，电脑重启后也可直接双击重新启动。

如需历史时点：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio show --as-of 2026-07-10
```

### 可审计时点快照

`show --as-of` 是即时重放视图；`snapshot` 则把本次重放结果连同输入状态哈希、引擎版本、价格来源和修订号保存到 SQLite。生成快照：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio snapshot `
  --as-of 2026-07-10
```

不传 `--knowledge-cutoff` 表示使用当前数据库中已经记录的全部信息，但交易生效日和价格日仍必须不晚于 `as_of`。如需模拟“当时已知信息”，传入带时区的 ISO 8601 截止时间：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio snapshot `
  --as-of 2026-07-10 `
  --knowledge-cutoff 2026-07-10T23:59:59+08:00 `
  --format json
```

P2B 对旧数据采用保守的 known-at 兼容规则：

- 成交使用 `ledger_entries.created_at`；
- 收盘价使用 `close_prices.fetched_at`；
- 用户确认现金使用 `cash_balance_snapshots.recorded_at`；
- 显式 knowledge cutoff 只纳入上述记录时间不晚于 cutoff 的数据；
- 这些字段表示“本地系统已记录/获取时间”，不冒充交易发生时用户已经知晓的时间。

读取默认最新修订或指定旧修订：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio snapshot-show `
  --as-of 2026-07-10

.\.conda\investment-system\python.exe -m src.portfolio snapshot-show `
  --as-of 2026-07-10 `
  --revision 1 `
  --format json
```

列出日期范围内的所有修订：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio snapshot-list `
  --from 2026-01-01 `
  --to 2026-12-31
```

快照口径：

- 交易只取 `event_date <= as_of`；显式 knowledge cutoff 时还要求 `created_at <= cutoff`；
- 行情只取 `trade_date <= as_of` 的最新合格记录，禁止未来价格回填；
- `staleness_days` 使用自然日差，价格日早于 `as_of` 即标为 `stale`；
- 无合格行情时数量和成本仍保存，价格、市值、未实现盈亏和权重为 `null`，状态为 `unpriced`；
- 组合 `market_value` 和 `unrealized_pnl` 是已定价明细小计；必须同时查看 `valuation_complete` 与 `unpriced_position_count`；
- 只有全部持仓均已定价且市值分母非零时才写入组合权重；
- 现金使用用户确认的历史锚点或由该锚点重放交割单生成的追加式快照；无合格记录时
  `cash_status=unavailable`，不会从总资产倒推；
- 已实现盈亏沿用现有移动加权成本引擎，范围是本地已记录台账自期初基准日起的累计值；
- 当前行业分类没有历史版本表，因此快照会记录其来源并明确标记为非 point-in-time；行业字段变化会形成新的 source-state hash。

相同账户、业务日、knowledge cutoff、引擎版本和 source-state hash 会返回已有快照，不重复写入明细。补录会影响该时点的旧交易、价格、现金或分类后，再次运行会生成下一 `revision`；旧修订不可覆盖或删除。组合汇总与明细在同一 SQLite 事务中写入，任一明细失败会整体回滚。

数据库 schema v7 新增 `portfolio_snapshots` 与 `position_snapshots`。首次从 v6 升级前会按既有规则在数据库旁生成单文件备份；快照仍只存在于被 Git 忽略的本地 SQLite 中。

## 3. 导入交割单

支持 `.csv`、`.tsv`、`.xlsx` 和二进制 `.xls`；部分券商把 GB18030 TSV 文本误命名为
`.xls`，导入器会先识别文件签名，再按制表符文本读取。程序会扫描文件前 40 行寻找表头，兼容常见中文列名：

- 日期：`成交日期`、`发生日期`、`交易日期`；
- 证券：`证券代码`、`证券名称`；
- 方向：`买卖标志`、`买卖方向`、`业务名称`；
- 成交：`成交数量`、`成交价格`、`成交金额`；
- 费用：优先使用 `手续费` 或 `费用合计`，否则汇总佣金、印花税、过户费、规费和其他费；
- 唯一标识：`成交编号`、`合同编号` 或 `流水号`。

始终先预览：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio import-statement `
  --input C:\path\to\statement.xlsx `
  --broker your_broker
```

预览无错误后再写入：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio import-statement `
  --input C:\path\to\statement.xlsx `
  --broker your_broker `
  --apply
```

预览结果中的 `cash_preview` 会同时披露现金锚点、买入流出、卖出流入、红利、现金费用和预计余额。
正式写入时，现金快照与成交台账在同一 SQLite 事务中生成；同一成交再次导入会按标准化字段哈希
去重，现金重放也以 ledger fingerprint 去重，不会重复扣款。计算口径为：

```text
现金余额 = 最近一次用户确认的日终现金
         - 买入成交金额 - 买入费用
         + 卖出成交金额 - 卖出费用
         + 现金红利 - 现金税费
```

交割单没有费用列、费用分项或可核对的资金发生额时，流水标记 `fees_missing=true`，自动现金仍会
暂算，但 `calculation_status=fee_pending`；取得正式交割单后应补齐费用并重新计算。若没有用户现金
锚点，或重放结果为负数，成交仍可入账，但不会生成自动现金快照，输出会保留明确状态与下一步。
`--included-in-opening` 和 `--historical-closed` 属于特殊历史模式，不改变当前现金。

`ledger` 可查看实际改变持仓的流水：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio ledger
```

组合内部从一个券商转托到另一个券商时，转出/转入不得写成 `SELL` / `BUY`。完成两端数量核对后，
使用内部托管迁移记录保存转出日、转入日、券商、数量、参考价和来源；该记录不改变组合数量、成本或盈亏。
查看已核对迁移：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio transfers
```

## 4. 期初快照已包含的旧交割单

只有在用户明确确认、或数量与成本勾稽能够证明时，才能认定期初快照已经反映某笔旧成交。成交日期早于快照提交日，并不等于成交已包含；快照提交日也不能自动作为会计截止日。

使用 `--included-in-opening` 前必须核对：`快照数量 = 交易前数量 + 买入 - 卖出`，并保留用户对“已包含/未包含”的明确说明。若用户确认旧成交未计入快照，应将会计基准日移到最早漏记成交之前，在影子数据库中按真实日期重放全部成交；不得用 `--included-in-opening` 省略数量和成本变化。

若要补齐来源追溯，可使用 `--included-in-opening`。这会登记成交明细，但不改变数量、成本或盈亏：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio import-statement `
  --input C:\path\to\old_statement.csv `
  --broker your_broker `
  --included-in-opening

.\.conda\investment-system\python.exe -m src.portfolio import-statement `
  --input C:\path\to\old_statement.csv `
  --broker your_broker `
  --included-in-opening `
  --apply
```

查看这类核对记录：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio reconciliations
```

若旧交割单属于基准日前的完整已清仓历史、需要进入清仓复盘和 K 线操作点，可使用 `--historical-closed`。该模式只接受“批次自身从零建仓、从不超卖、最终数量归零、且每条日期均不晚于基准日”的流水；不满足任一条件都会拒绝写入。历史盈亏会出现在清仓周期中，但不会计入“基准日以来已实现盈亏”。仍须先预览，再应用：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio import-statement `
  --input C:\path\to\historical_closed.csv `
  --broker your_broker `
  --historical-closed

.\.conda\investment-system\python.exe -m src.portfolio import-statement `
  --input C:\path\to\historical_closed.csv `
  --broker your_broker `
  --historical-closed `
  --apply
```

## 5. 成本和盈亏口径

当前采用券商摊薄成本，并以日终持仓是否归零作为周期边界：

```text
买入后剩余成本 = 原剩余成本 + 买入成交金额 + 买入费用
卖出后剩余成本 = 原剩余成本 -（卖出成交金额 - 卖出费用）
现金红利后成本 = 原剩余成本 - 现金红利
现金税费后成本 = 原剩余成本 + 现金税费
浮动盈亏       = 最新收盘价 × 当前数量 - 当前剩余成本
```

只要持仓周期仍开放，卖出净额、现金红利和现金税费都滚入剩余成本。只有日终持仓真正归零时，
才把完整周期结果确认为已实现盈亏。经过人工复核的券商成本快照可登记为成本锚点；锚点必须保留
`source_path`、目标数量、状态和说明，数量不一致或 `unverified` 的锚点不得进入核算。

### 清仓收益

“清仓收益”不是另一套手工维护的数据，而是每次打开页面时从成交台账重放得到：

```text
完整清仓周期 = 持仓数量从 0（或期初快照）变为正数，最终在某个交易日日终归零
清仓净卖出额 = 周期内全部卖出成交金额 - 卖出费用
清仓收益     = 清仓净卖出额 - 周期取得成本 + 周期内现金红利 - 周期内现金税费
清仓收益率   = 清仓收益 / 周期取得成本
```

日内卖出使数量短暂归零、随后同日买回，仍属于同一持仓周期，相关盈亏继续反映在摊薄成本中。
只有日终归零后，下一交易日或更晚再次买入才开启新周期，并以“第 2 轮、第 3 轮”分别保留。
页面列表先按证券合计清仓数量、结转成本、净卖出额、清仓收益和收益率；点击证券汇总行后，
下拉子列表逐次展示完整清仓周期，单次周期仍可进入详情抽屉复盘。

命令行查看：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio closed
.\.conda\investment-system\python.exe -m src.portfolio closed --as-of 2026-07-12
.\.conda\investment-system\python.exe -m src.portfolio closed --format json
```

期初快照和经过复核的成本锚点原样继承券商显示的摊薄总成本；后续成交、红利和税费继续按上述
摊薄口径滚动。缺少费用的交割单必须保留 `MISSING_SOURCE_COLUMN`，不能覆盖更高质量的已复核成本锚点。

## 6. 安全检查与当前限制

- 普通交割单中，成交日不晚于期初基准日时拒绝写入；
- 上述日期拦截只是防重复技术门槛，不是“已包含”的会计证据；漏记旧成交必须经过备份、影子库重放、未受影响持仓对比和网页 API 复核后再换库；
- 卖出数量超过当时持仓时，整批回滚；
- 只有日终数量实际归零时才生成清仓周期；日内临时归零以及仍持有的部分卖出不会被误标为清仓；
- 任一解析错误都会阻止整批写入；
- 信用交易、融资融券、红股、送股、转增、证券转入转出不会猜测成本，需人工明确口径；
- 行情更新默认要求每只持仓都找到价格；停牌证券可用 `--allow-partial` 明确允许部分缺失；
- `refresh-prices --as-of YYYY-MM-DD` 取得该日期或此前的最新可得收盘价，不抓取盘中价。
- 持仓数据库从 v4 升级到 v5 时新增分钟刷新批次和分钟行情观察表；从 v5 升级到 v6 时新增
  `internal_transfer_reconciliations`，所有迁移前均用 SQLite backup API 生成一个带版本和时间戳的单文件备份；
- K 线刷新要求 OHLC 与所需复权因子同时校验通过后才原子写入；上游失败保留已有缓存；
- 分钟行情保持追加式写入，同一结束时间按最新观察读取；重复刷新相同观察保持幂等，双源失败保留已有缓存；
- 可视化页面和 API 仅绑定 `127.0.0.1` 或 `localhost`；写操作需要页面专用请求头，不提供跨域访问。

## 7. 导出

```powershell
.\.conda\investment-system\python.exe -m src.portfolio show --format json `
  --output C:\path\to\portfolio.json

.\.conda\investment-system\python.exe -m src.portfolio show --format csv `
  --output C:\path\to\portfolio.csv
```
