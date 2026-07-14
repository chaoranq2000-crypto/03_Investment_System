# Portfolio Tracker — 本地持仓与交割单操作手册

## 1. 定位与边界

`src/portfolio/` 是一个本地、只做记录和核算的持仓台账：

- 用期初快照建立持仓；
- 用 Tushare 更新每只证券的最新可得收盘价；
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

更新行业标签：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio refresh-industries
```

行业透视遵循可追溯分类，不做无来源猜测：

- 普通股票使用 Tushare `stock_basic.industry`；
- 主题 ETF 若名称含有明确行业属性，则归入对应行业，例如医药、互联网、半导体或证券；
- 宽基、跨行业或名称中没有可靠行业属性的 ETF 保留为 `未分类（ETF）`；
- 每只证券保存 `industry_source` 和 `industry_updated_at`；行业标签是当前分类，不随历史回看日重放。

启动本地可视化页面：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio web
```

页面默认在 `http://127.0.0.1:8765/` 打开，提供持仓总览、资产占比、盈亏贡献、行业透视、清仓收益、证券筛选与排序、历史时点查看、隐私遮罩和 CSV 导出。最新视图会在页面可见时每 60 秒刷新一次盘中行情；页面中的“更新收盘价”和“更新行业”仍分别调用正式收盘价与行业刷新逻辑。按 `Ctrl+C` 停止服务。

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

Windows 桌面快捷启动使用 `scripts/start_portfolio_dashboard.ps1`。当前电脑的桌面快捷方式是 `C:\Users\Q\Desktop\持仓账本.lnk`：双击后会先检查本地服务；若服务尚未运行，则在后台隐藏启动，健康检查通过后再打开默认浏览器。这个过程不依赖 Codex，电脑重启后也可直接双击重新启动。

如需历史时点：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio show --as-of 2026-07-10
```

## 3. 导入交割单

支持 `.csv`、`.tsv`、`.xlsx`；`.xls` 是否可读取取决于本地 pandas Excel engine。程序会扫描文件前 40 行寻找表头，兼容常见中文列名：

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
- 可视化页面和 API 仅绑定 `127.0.0.1` 或 `localhost`；写操作需要页面专用请求头，不提供跨域访问。

## 7. 导出

```powershell
.\.conda\investment-system\python.exe -m src.portfolio show --format json `
  --output C:\path\to\portfolio.json

.\.conda\investment-system\python.exe -m src.portfolio show --format csv `
  --output C:\path\to\portfolio.csv
```
