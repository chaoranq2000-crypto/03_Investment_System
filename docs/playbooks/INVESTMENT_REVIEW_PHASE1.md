# 投资复盘系统 Phase 1：可追溯数据底座

## 1. 本补丁解决什么

固定提交 `a12cbb8a9b90e348c117f8eff3087a5a89c5c1b3` 已经具备本地持仓台账、成交导入、成本重算、行情刷新和可视化能力。本补丁不重写这些能力，而是在旁边增加一个独立的复盘数据层：

```text
现有 portfolio 数据库（只读）
            │
            ├── doctor：扫描表、字段和候选成交表
            │
            └── mapping-driven ingest
                        ↓
data/db/investment_review.sqlite3（独立旁路库）
            ├── data_sources / source_config_versions
            ├── ingest_runs / ingest_run_events
            ├── trade_events（gross_amount 与 cash_amount 分列）
            ├── decisions / decision_event_links
            └── snapshots（预留统一契约）
```

这一阶段只回答三件事：

1. 数据来自哪里；
2. 事情何时发生、你何时知道；
3. 同一条源记录是否被稳定、无冲突地导入。

不做 AI 心理归因、不做交易评分、不生成买卖建议，也不改动现有持仓计算口径。

## 2. 为什么使用独立旁路库

- 对现有持仓库保持只读，降低回归风险；
- 复盘模型可以独立演进，不污染会计与持仓计算；
- 所有导入都有 source、run、raw payload 和 SHA-256；
- 同一源记录重复导入会跳过，内容漂移会明确报错；
- 后续可以在不改原始台账的情况下重建 Trade Episode、组合快照和行为序列。

## 3. 首次运行

PowerShell：

```powershell
.\scripts\start_investment_review.ps1 init

.\scripts\start_investment_review.ps1 doctor `
  --portfolio-db data/db/<你的持仓数据库>.sqlite3 `
  --out reports/investment_review/phase1/schema_manifest.json `
  --mapping-out config/investment_review.portfolio.generated.json
```

启动脚本优先使用当前 checkout 的 `.conda\investment-system`；在 linked
worktree 中会继续查找主工作树的同名 conda 环境，最后才回退到当前
conda/PATH 中的 `python`。也可以通过 `-Python <path>` 显式指定解释器。

也可以直接运行：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  --db data/db/investment_review.sqlite3 `
  doctor `
  --portfolio-db data/db/<你的持仓数据库>.sqlite3 `
  --mapping-out config/investment_review.portfolio.generated.json
```

`doctor` 使用 SQLite `mode=ro`，不会向持仓数据库建表、写 WAL 或更新版本号。生成的 mapping 只是建议，只能用于 `--dry-run`；formal import 会拒绝 `review_required=true` 且没有完整人工审核锁的 generated mapping。审核时必须检查五个核心字段：

- `occurred_at`
- `symbol`
- `side`
- `quantity`
- `price`

保留 `config/investment_review.portfolio.generated.json` 作为机器建议，审核后另存为
`config/investment_review.portfolio.reviewed.json`。reviewed mapping 必须记录 reviewer、审核时间、
schema manifest 路径与 SHA-256、generated mapping 路径与 SHA-256，并用
`review.mapping_content_sha256` 锁定完整审核文档（计算时仅排除该自引用字段）。当前正式台账的现场审核结果为：

- `record_id = account_id + "::" + external_id`，以账户内的外部记录 ID 建立稳定源身份；
- `occurred_at = event_date + event_time`；
- `side = event_type`，同时保留真实 `event_type`；
- `DIVIDEND` / `CASH_FEE` 的 `side` 为 `OTHER`，不误标成 fill，并把来源
  `cash_amount` 保存在独立 canonical 字段中；
- `created_at` 是台账重建时间，不是真实历史知悉时间，因此 `known_at`
  留空并显式记录 `known_at_fallback=true`。
- formal SQLite import 同时锁定实际来源文件、`source.uri`、`generated_from.database`、
  `sqlite.table` / `generated_from.table` 和表结构 SHA-256；当前 `ledger_entries` 的
  `table_schema_sha256` 为
  `26a979d503a276afa0e42957c90878eb479ab63bcd7d59374366525c959c79bf`。

以上只适用于本次 schema manifest；若正式台账结构变化，必须重新运行
`doctor` 和人工审核，不能沿用旧 mapping。

## 4. 先预演，再导入

```powershell
.\scripts\start_investment_review.ps1 ingest-sqlite `
  data/db/<你的持仓数据库>.sqlite3 `
  --mapping config/investment_review.portfolio.reviewed.json `
  --dry-run
```

确认预览中的 BUY、SELL、DIVIDEND、CASH_FEE 代表样本，以及代码、方向、数量、
价格、`gross_amount`、`cash_amount` 和时间都正确后，再去掉 `--dry-run`。

```powershell
.\scripts\start_investment_review.ps1 ingest-sqlite `
  data/db/<你的持仓数据库>.sqlite3 `
  --mapping config/investment_review.portfolio.reviewed.json
```

CSV 券商交割单也可直接使用：

```powershell
Copy-Item config/investment_review.example.json config/investment_review.local.json
# 修改 local mapping；source.identity_key 必须是稳定的券商/账户/导出命名空间，
# 不能使用会随复制或重命名变化的 CSV 文件路径

.\scripts\start_investment_review.ps1 ingest-csv `
  data/imports/<交割单>.csv `
  --mapping config/investment_review.local.json `
  --dry-run
```

CSV mapping 的 `record_id` 是必填字段；`source.identity_key` 参与稳定 source identity，
使同一份导出文件复制或改名后不会被当成新的来源并重复导入。路径只记录本次读取位置，
不能代替稳定身份。

## 5. 捕获决策上下文

成交记录通常没有“为什么”。可在操作发生后尽快补充：

```powershell
.\scripts\start_investment_review.ps1 note-add `
  --symbol 600000.SH `
  --occurred-at "2026-07-14 10:05:00" `
  --known-at "2026-07-14 10:08:00" `
  --thesis "示例：盈利预期变化驱动，等待后续数据验证" `
  --invalidation "示例：关键订单或利润率假设被证伪" `
  --horizon "1-3 months" `
  --portfolio-role "event-driven" `
  --direct-reason "示例：首次建仓"
```

`occurred_at` 是事情发生时间，`known_at` 是你实际知道或记录它的时间。
`note-add` 要求显式提供 `--known-at`，不会把当前时间或 `occurred_at` 静默写成历史知悉时间。
后续复盘查询必须按 `known_at` 截断，避免事后信息泄漏。

## 6. 验收命令

```powershell
python -m unittest tests.test_investment_review_phase1 -v
.\scripts\start_investment_review.ps1 status
```

通过标准：

- `integrity_check` 为 `ok`；
- 同一数据重复导入时 `inserted=0`、`skipped>0`；
- 同一源记录 ID 内容改变时原子失败，不保留部分新记录；
- 持仓源库在 doctor/ingest 后文件大小和修改时间不变；
- generated mapping 的 formal import 被拒绝，reviewed mapping 的 provenance 与
  `mapping_content_sha256` 均通过；
- 旁路库为 schema v2，`application_id=0x49525657`（`IRVW`）；把持仓库误传给
  `--db` 时必须在建表或写 WAL 前拒绝；
- legacy v1 旁路库不得自动升级，因为旧 schema 无法重建完整 event-run lineage；
  必须新建 v2 sidecar 并从只读来源重新导入；
- 每条事件可通过 `ingest_run_events` 显式追溯到 source、source record、raw payload
  和每次 ingest run；
- `known_at` 不早于 `occurred_at`。

## 7. 当前明确不做

- 不自动推断现有持仓库中所有表的业务含义；
- 不自动把成交聚合成 Trade Episode；
- 不计算行为标签、心理诊断或复盘总分；
- 不接入 LLM 生成结论；
- 不修改 portfolio Web UI；
- 不提供买卖、仓位或收益保证建议。

这些边界保证第一步可审查、可回滚，并为下一步“决策事件重构 + 组合快照”提供稳定输入。
