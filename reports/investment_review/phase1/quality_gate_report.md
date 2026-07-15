# Investment Review Phase 1 Quality Gate

## Outcome

`accepted_with_todos`

- open critical：0
- open high：0
- accepted medium TODO：4
- accepted low TODO：1
- resolved high：16
- independent final review：passed for the current four-run snapshot

## Local checks

| local_check_id | result | evidence |
|---|---|---|
| `QR-IR-1` | pass | 补丁哈希、基线和 23 个内部校验值已验证。 |
| `QR-IR-2` | pass | 正式源库以 `mode=ro` 访问；doctor、dry-run、四次导入前后 hash / size / mtime 不变。 |
| `QR-IR-3` | pass | 稳定源 ID 使用 `account_id::external_id`；非交易事件保留 event type，`cash_amount` 与 `gross_amount` 分列。 |
| `QR-IR-4` | pass_with_todo | 双时间约束无倒置，但历史真实 `known_at` 缺失，961 条均显式 fallback。 |
| `QR-IR-5` | pass_with_todo | 首次插入 961；三次复跑均插入 0、跳过 961；稳定身份内容漂移与全量快照移除检测由测试覆盖，增量 CSV 语义仍需显式模式。 |
| `QR-IR-6` | pass_with_todo | 961 个事件与 4 个 run 形成 3844 条显式 `ingest_run_events`；首次 run 与 payload SHA 校验无缺口，但完整 source_row hash 可能保守误报技术字段漂移。 |
| `QR-IR-7` | pass | schema v2、`application_id=0x49525657`、integrity check 为 ok、foreign-key issues 为 0；wrong DB 在写入前拒绝。 |
| `QR-IR-8` | pass_with_todo | 不编造决策上下文；当前 decisions=0，未来仅接受用户确认的 note。 |
| `QR-IR-9` | pass | no-advice 边界通过；无交易指令、仓位建议、目标价或保证收益。 |
| `QR-IR-10` | pass | `AGENTS.md` 已显式启用独立 `investment-review` 路由，并隔离 research workflow / P2 / order execution。 |
| `QR-IR-11` | pass_with_todo | Gate 2–5 未启动；启用 `position_snapshot_items` 前仍需处理 nullable market 复合主键。 |
| `QR-IR-12` | pass | generated mapping 只能 dry-run；formal import 会验证 reviewer、审核时间、schema/generated SHA 与完整文档内容锁。 |
| `QR-IR-13` | pass | account、market、cash_amount 与完整 source config 参与漂移判断；3 个 config version 均保留。 |
| `QR-IR-14` | pass | 代表性预览覆盖 BUY、SELL、DIVIDEND、CASH_FEE，避免仅显示前几条交易事件。 |
| `QR-IR-15` | pass | `note-add` 要求显式 `known_at`，不会静默回填历史知悉时间。 |
| `QR-IR-16` | pass | formal SQLite import 将真实源文件绑定到 reviewed `source.uri` / `generated_from.database`，并校验 table 与实时 schema hash。 |
| `QR-IR-17` | pass | CSV 要求稳定 `source.identity_key`，所有 mapping 要求显式 `record_id`。 |
| `QR-IR-18` | pass | legacy v1 不自动迁移；拒绝原地修改并要求新建 v2 sidecar 后重新导入。 |

## Resolved high issues

| issue_id | resolved risk | current evidence |
|---|---|---|
| `ir_p1_qr_001` | skill 路由与根政策冲突 | `AGENTS.md` 显式启用隔离的 repo-local utility。 |
| `ir_p1_qr_002` | generated mapping 可直接 formal import | generated 仅允许 dry-run，formal import 实测拒绝。 |
| `ir_p1_qr_003` | source / reviewed mapping provenance 不完整 | source、schema manifest、generated mapping 与 reviewer 元数据均锁定。 |
| `ir_p1_qr_004` | mapping 审核后可 TOCTOU 漂移 | `mapping_content_sha256` 覆盖完整审核文档，仅排除自引用字段。 |
| `ir_p1_qr_005` | account / market / config drift 未比较 | 所有持久化字段与完整 config fingerprint 纳入检测，版本不静默覆盖。 |
| `ir_p1_qr_006` | 现金事件被压成零 gross amount | 独立 canonical `cash_amount`，DIVIDEND=6465.15、CASH_FEE=369.49。 |
| `ir_p1_qr_007` | 决策 note 可静默回填 known_at | `note-add --known-at` 必填，非有限数值也拒绝。 |
| `ir_p1_qr_008` | 错误 `--db` 可能污染 portfolio 库 | schema v2 application lock 在建表、WAL 前拒绝非 review DB。 |
| `ir_p1_qr_009` | event → ingest run 只有时间窗推断 | 3844 条显式 run-event 关联，首次 INSERTED link 完整。 |
| `ir_p1_qr_010` | `dedupe_key` 作为内容型源身份 | 改用 `account_id::external_id`；内容漂移仍单独检查。 |
| `ir_p1_qr_011` | 来源记录移除无法检测 | 以前一 run membership 为基线检测 removed snapshot。 |
| `ir_p1_qr_012` | dry-run 前五条掩盖非交易类型 | 代表性 preview 按事件类型取样并显示 `cash_amount`。 |
| `ir_p1_qr_013` | formal SQLite 来源可替换路径、表或 schema | 同文件路径判定、table 一致性与 `table_schema_sha256` 共同绑定。 |
| `ir_p1_qr_014` | CSV 文件复制或改名可产生新 source identity | 强制稳定 `source.identity_key`，路径不再决定身份。 |
| `ir_p1_qr_015` | legacy v1 原地迁移无法补建 lineage | application/schema lock 拒绝自动升级，要求新 v2 sidecar 重导。 |
| `ir_p1_qr_016` | mapping 可缺失稳定 source record ID | `record_id` 加入所有导入的必需字段集合。 |

## Accepted TODO boundary

1. medium：`payload_sha256` 基于完整 `source_row`；台账仅技术字段重建也可能触发保守的安全性假冲突，必须人工核查，不能自动放行。
2. medium：当前所有 source 默认采用全量 snapshot removal 语义；月度增量 CSV 需要未来显式 `snapshot_mode=full|append` 后才能安全使用。
3. medium：961 条历史 `known_at` 只有显式 fallback；后续需要 `known_at_quality` / precision，当前不代表真实当时知悉时间。
4. medium：`decisions=0`，不能从成交反推历史动机。
5. low：精确 adapter、Episode 与组合快照属于 Gate 2；启用 `position_snapshot_items` 前必须处理 nullable `market` 复合主键，Gate 2 当前整体未启动。

这些 TODO 不阻断 Phase 1 数据底座，但会限制后续分析可信度。它们必须在进入
Episode、组合快照或 AI 解释前继续可见，不得通过默认值或叙事隐藏。独立终审已确认
当前结果；后续若出现新的 critical / high，必须重新打开 Gate 1，而不是维持本结论。
