# Portfolio Tracker — 本地持仓与交割单操作手册

## 1. 定位与边界

`src/portfolio/` 是一个本地、只做记录和核算的持仓台账：

- 用期初快照建立持仓；
- 按日期记录用户确认的账户现金余额，并保留历次快照；
- 用 Tushare 更新每只证券的最新可得收盘价；
- 按需缓存前复权日 K 线和单日分钟行情，并在所选持仓周期内标注事实型操作点；
- 用券商 CSV/XLSX 交割单更新数量、剩余成本和基准日后已实现盈亏；
- 自动识别持仓数量归零的完整清仓周期，并计算清仓收益；
- 保留成交、行情和导入批次，支持去重和历史时点重放；
- 不下单，不生成买入、卖出、持有或仓位建议。

默认数据库是 `data/db/portfolio.sqlite3`。`data/db/` 下的 SQLite、CSV 和 Excel 文件均被 Git 忽略，个人持仓和交割单不会进入公开仓库。

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

记录当前现金余额（来源标记为 `user_provided`，不会从成交额反推）：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio set-cash `
  --amount 12345.67 `
  --as-of 2026-07-14 `
  --note "用户确认当前现金余额"

.\.conda\investment-system\python.exe -m src.portfolio cash
```

同一天重复记录不会覆盖旧值；页面和历史回看会选择截止日以前最新录入的快照。
总资产按“证券市值 + 现金余额”展示，证券成本与盈亏口径不受现金快照影响。

更新行业标签：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio refresh-industries
```

行业透视遵循可追溯分类，不做无来源猜测：

- 股票使用 Tushare `stock_basic.industry`，再通过
  `config/portfolio_industry_taxonomy.json` 归一到可合并行业；例如 `化学制药`、`生物医药`统一为
  `医药生物`，原始标签仍保存在 `industry_source`；
- ETF 优先使用交易所每日申赎篮子 `etf_sh_cons` / `etf_sz_cons`，按成分数量乘同日收盘价计算
  可比较权重；不可用时回退到 `fund_portfolio` 最近一期披露持仓；
- 港股成分在 Tushare 缺少行业字段时，批量回退到东方财富港股 F10 的 `BELONG_INDUSTRY`；
  同日港股收盘价回退到 AKShare 封装的新浪 `stock_hk_daily`。两项来源都会写入分类元数据，接口失败
  只会降低覆盖率，不会触发名称猜测；
- 对平台型主题 ETF，可在持仓覆盖先达标后启用配置化主题聚合。例如跟踪指数明确含 `互联网`，且
  `互联网 / 专业零售 / 传媒 / 电子` 的成分权重合计不低于 80%，才合并为 `互联网`；指数名称只负责
  选择已审定规则，不能单独形成分类；
- 已分类权重覆盖率和成分数量覆盖率都不低于 70% 后才判断主行业：第一行业权重不低于 80%
  为高置信度，60% 至 80% 为中置信度，低于 60% 标记为 `跨行业ETF`；
- 覆盖不足、跨市场成分仍缺少已复核行业来源或无法形成可比较权重时，标记为
  `未分类（ETF持仓覆盖不足）`；ETF 名称和跟踪指数仅作佐证，不替代持仓证据；
- 每只证券保存 `industry_source` 和 `industry_updated_at`；行业标签是当前分类，不随历史回看日重放。

启动本地可视化页面：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio web
```

页面默认在 `http://127.0.0.1:8765/` 打开，提供持仓总览、资产占比、盈亏贡献、行业透视、清仓收益、证券筛选与排序、历史时点查看、隐私遮罩和 CSV 导出。点击行业透视中的行业行可展开对应持仓证券，并可继续进入单只证券详情；资产总览、市值分布、盈亏贡献、行业透视、清仓收益和持仓明细六个模块均可独立折叠，折叠状态保存在当前浏览器。最新视图会在页面可见时每 60 秒刷新一次盘中行情；页面中的“更新收盘价”和“更新行业”仍分别调用正式收盘价与行业刷新逻辑。按 `Ctrl+C` 停止服务。

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

同一成交再次导入会按标准化字段哈希去重。`ledger` 可查看实际改变持仓的流水：

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

当前采用移动加权平均成本：

```text
买入后剩余成本 = 原剩余成本 + 买入成交金额 + 买入费用
卖出结转成本   = 卖出数量 × 卖出前平均成本
卖出已实现盈亏 = 卖出成交金额 - 卖出费用 - 卖出结转成本
浮动盈亏       = 最新收盘价 × 当前数量 - 当前剩余成本
```

现金红利记入基准日后已实现盈亏，但不修改持仓成本；红利税费单独扣减。

### 清仓收益

“清仓收益”不是另一套手工维护的数据，而是每次打开页面时从成交台账重放得到：

```text
完整清仓周期 = 持仓数量从 0（或期初快照）变为正数，最终再次归零
清仓净卖出额 = 周期内全部卖出成交金额 - 卖出费用
清仓收益     = 清仓净卖出额 - 卖出结转成本 + 周期内现金红利 - 周期内现金税费
清仓收益率   = 清仓收益 / 周期内全部卖出结转成本
```

部分卖出后仍有持仓时，该笔已实现盈亏仍会进入顶部“基准日后已实现盈亏”，但不会提前标成完整清仓收益。清仓后再次买入同一证券会开启新的周期，并以“第 2 轮、第 3 轮”分别保留。

命令行查看：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio closed
.\.conda\investment-system\python.exe -m src.portfolio closed --as-of 2026-07-12
.\.conda\investment-system\python.exe -m src.portfolio closed --format json
```

部分券商界面展示的是“摊薄成本价”，可能把历史已实现亏损摊回剩余股份，和本工具的移动加权平均成本不同。期初快照会原样继承券商显示的总成本；基准日后的成交则统一按上述口径计算。

## 6. 安全检查与当前限制

- 普通交割单中，成交日不晚于期初基准日时拒绝写入；
- 上述日期拦截只是防重复技术门槛，不是“已包含”的会计证据；漏记旧成交必须经过备份、影子库重放、未受影响持仓对比和网页 API 复核后再换库；
- 卖出数量超过当时持仓时，整批回滚；
- 只有数量实际归零时才生成清仓周期；仍持有的部分卖出不会被误标为清仓；
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
