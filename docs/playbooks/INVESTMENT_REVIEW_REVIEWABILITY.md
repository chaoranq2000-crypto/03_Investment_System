# Investment Review 可审核性修正操作手册

## 1. 定位

本手册定义 `investment_review_product_completion_v3` 的可审核性 overlay。它在既有
Phase 1、P2C、P2E-3、P2F 和 product-completion v2 之上增加新的投影，不修改旧对象、
旧 validator 或旧 artifact bytes，也不是 P2H Stage 2 Slice B。

唯一候选库为显式选择的全新 sidecar。core v2、product-completion v1 与
reviewability v1 是三个独立 marker。普通 `initialize()` 和
`initialize_product_completion()` 不得创建 reviewability 表；已有用户 sidecar、v2
candidate、legacy 或缺少完整 marker/结构的库必须先只读检查并拒绝，不能静默升级或修复。

新候选路径只能通过 `O_CREAT | O_EXCL` 取得所有权；初始化期间保持该文件描述符打开，并在
SQLite 连接前、连接后、启用 WAL 后及提交后用 `fstat/stat + samestat` 证明始终是同一个
文件。既有路径只允许先用 `mode=ro&immutable=1` 检查；非空 `-wal` 或无配对 WAL 的
`-shm` 必须拒绝。Windows 普通只读 status 留下的稳定零字节 WAL 及配对 SHM 可以保留，
但必须在检查前后逐一核对辅助文件的 identity、size、纳秒 mtime 和 SHA-256；任何辅助
状态/字节变化或非空 WAL 都拒绝。immutable 连接前后还要分别记录主库文件 identity、
size、纳秒 mtime 和 SHA-256，只有 `samestat`、大小、mtime 与 hash 全部不变才接受。
由于 immutable SQLite 可能报告 `journal_mode=delete`，还必须
由主库持久化 header 独立证明 WAL。候选库必须保持
`journal_mode=WAL`，且 `PRAGMA quick_check` 精确返回 `ok`。冻结的完整 foundation
manifest 覆盖 core、product-completion 和 reviewability 的全部非内部
table/index/trigger/view，以及 `table_xinfo`、foreign key、`index_list/index_xinfo`
（包括隐式索引）；其固定 SHA-256 为
`e1241c55fe615a0389b9f7ee2c8d0e7071d7c45487800d67b00d29f53dcceab0`。marker 或完整
manifest 任一不匹配都必须拒绝；每次保存还必须在同一个 `BEGIN IMMEDIATE` 可写事务中
重验，不能用较早的只读检查替代。

## 2. 七个顺序门禁

| 阶段 | 本阶段新增权限 | 尚未授权 |
|---|---|---|
| P1 | skill、手册、checkpoint schema、空的 additive schema/marker、fixture tests | 真实 sync、runner、snapshot、market、automation、API/UI |
| P2 | 只按数量变迁和显式事件分类操作；Decision 可缺失 | 推断理由、snapshot、market、open 调度、Web/UI |
| P3 | user/system perspective 与四时间 provenance；首次写全新 candidate | 修改 mapping 语义、把晚录入倒填为系统当时观察 |
| P4 | 从完整同步账本重建 pre/post/cutoff 持仓 | 写正式 snapshot 表、补造 cash/price/NAV |
| P5 | episode-scoped、append-only open/adjustment/exit checkpoint | 跨 episode 自动合并、伪造退出或最终结果 |
| P6 | 本地优先市场装配；满足触发条件时受控 provider 补齐 | renderer/replay/API/UI 联网、正式行情库写入 |
| P7 | 六轴 API/UI、证据抽屉、可关闭的进程内 catch-up | OS scheduler/service、生产发布、P2H UI |

每一阶段都要求前一 checkpoint、targeted tests、受保护源检查和干净 tracked tree。代码
存在或命令可调用不等于门禁通过。

## 3. 操作事实与决策背景

操作类型只由事件前后数量与显式事件事实派生：

- `0 -> 正数`：`position_open`；
- `正数 -> 更大正数`：`position_increase`；
- `正数 -> 更小非负数`：`position_reduce`；
- `正数 -> 0`：`position_close`；
- 现金事件保持现金事件；
- 同时反转、负仓、修正链或业务顺序不可证明时保持 `ambiguous`/`blocked`。

这些标签只描述账户操作，不描述投资理由。没有 Decision 或理由时仍可
`operation=ready`，而 `decision=not_recorded` 或 `not_applicable`。不得自动创建空
Decision、thesis、motive、心理解释或建议。

## 4. 四时间与 perspective

每条进入 checkpoint 的材料都必须保留以下时间及依据：

| 字段 | 含义 |
|---|---|
| `effective_at` / `occurred_at` | 账户或市场事实实际生效时间 |
| `user_known_at` | 决策者视角可见时间 |
| `system_observed_at` | 有真实系统采集/观察证据的时间 |
| `recorded_at` / `ingested_at` | 写入来源或 sidecar 的时间 |

每个时间都带 `basis` 和 `source_refs`。账户所有者的无冲突操作可使用
`owner_action_default`，此时 `user_known_at=effective_at`；它不能证明系统当时观察，也
不能用于市场数据。晚录入保留真实的 system/recorded 时间，不倒填。

时间 basis 不仅是闭合集合，还按字段收窄：

| 时间字段 | 有值时允许的 `basis` |
|---|---|
| `effective_at` | `source_occurred_at | source_effective_at` |
| `user_known_at` | `owner_action_default | explicit_user_record | source_occurred_at | source_effective_at` |
| `system_observed_at` | `system_observation | recorded_later | ingest_observation` |
| `recorded_at` | `recorded_later | ingest_observation | system_observation` |

有时间值时必须有来源；`not_observed/unknown` 只能用于允许为空且确实为空的时间。
`effective_at` 与 `recorded_at` 不可为空。四个时间必须满足
`effective_at <= as_of <= knowledge_cutoff`，且
`effective_at <= user_known_at/system_observed_at/recorded_at <= knowledge_cutoff`（可空
时间除外）。

市场时间另行保留 `effective_at`、`publicly_available_at` 及
`publicly_available_basis`、`fetched_at`、`system_observed_at`。公开时间、抓取时间和
系统观察时间不能互相代替；`reconstructed_public_context` 必须有真实 `fetched_at`，
`system_known_at_decision` 必须有 cutoff-safe 的真实 `system_observed_at`。

runner 必须显式选择 `user` 或 `system` perspective；perspective、cutoff 与相关输入 hash
进入 run key、artifact 和 source replay。现有 `CanonicalTradeEvent.event_id`、reviewed
mapping 和旧 `known_at` 字节保持不变，v3 通过 additive projection表达新语义。

## 5. 六个独立状态轴

1. `operation`：`ready | partial | blocked`。
2. `decision`：`complete | partial | not_recorded | not_applicable | blocked`。
3. `snapshot_cash_valuation`：总状态之外，`position_quantity`、`cost_basis`、`cash`、
   `price`、`nav`、`weight`、`industry` 分别为
   `available | partial | missing | not_applicable`。
4. `market`：availability 与
   `system_known_at_decision | reconstructed_public_context | withheld | missing`
   的 temporal role 分开。
5. `lifecycle`：`open | closed | ambiguous | unknown`。
6. `outcome`：`interim | final | not_applicable | missing`。

轴之间不能互相污染。以下组合是正常且可完成操作复盘的状态：

```text
operation=ready
decision=not_recorded
snapshot_cash_valuation=partial
market=missing
lifecycle=open
outcome=interim
```

material 状态必须带自身证据。根 `source_refs` 始终非空；
operation 的 `ready/partial`、decision 的 `complete/partial`、snapshot 聚合的
`available/partial`、每个 snapshot 字段的 `available/partial`、market 的
`available/partial/stale/insufficient`、lifecycle 的 `open/closed`、outcome 的
`interim/final` 都要求非空 `source_refs`；`market=available` 还必须有
`effective_at`。`decision=not_recorded` 可无 Decision 来源，因为它明确表达“没有记录”，
而不是伪造一条 Decision。

`snapshot_cash_valuation.status` 必须由七个字段状态聚合：

- `available`：每个字段只能是 `available` 或 `not_applicable`，且至少一个字段为
  `available`；
- `missing`：每个字段只能是 `missing` 或 `not_applicable`，且至少一个字段为
  `missing`；
- `partial`：至少一个字段为 `available`，且至少一个字段为 `partial` 或 `missing`；
- `blocked`：只在对应的轴阻断 gap 可证明时使用。

字段 `available` 必须同时有非空字符串值和来源；`missing/not_applicable` 的值必须为
null。任何 binary float、缺失补零或“因 NAV 缺失而隐藏可用数量”的投影都拒绝。

`OPEN_EPISODE_OUTCOME_NOT_FINAL` 只能作为不影响 readiness 的说明，不能作为 gap。
每个真正 gap 必须有 `axis`、稳定 `code`、`severity`、`blocks_axis`、`owner`、
`next_step` 和 `source_refs`。`blocks_axis=true` 时 `source_refs` 必须非空，并且必须同时
`severity=blocker`，并把对应轴置为：operation/decision/snapshot 的 `blocked`，
market 的 `failed`，lifecycle 的 `ambiguous`，或 outcome 的 `missing`；不能用一个轴
的 blocker 污染另一个轴。

## 6. 账本快照

快照从全量同步的新 candidate 事件重建，并用正式 portfolio DB 的只读证据核对。不得调用
会写正式库的 snapshot builder。每个 pre/post/checkpoint 锚点保存：

- 事件集合、cursor scope、基准和 source hash；
- 持仓数量与成本；
- 现金、价格、NAV、权重和行业的独立 availability；
- 同时点缺少业务顺序、公司行动、opening baseline 或 partition cursor 限制。

已证明的持仓不能因现金或价格缺失而隐藏。缺失不得补零；priced subset 不得伪造成完整
NAV/权重；当前行业必须标记非 point-in-time。

## 7. 开放持仓 checkpoint

checkpoint 的语义身份以 episode 为根，只由 `episode_id`、`review_kind`、
`checkpoint_type`、`perspective`、`as_of` 和 `knowledge_cutoff` 计算。
`position_case_id` 是内容与投影字段，不参与身份，也不能在同一语义 cutoff 下另建分叉：
换 case 仍命中同一 key/唯一约束，内容不同必须报 conflict。不同 cutoff 才能创建新记录；
旧 checkpoint 永远 create-only。默认禁止跨 episode 合并再入场。

`review_kind`、`checkpoint_type`、lifecycle 与 outcome 必须兼容：

- `review_kind=active_checkpoint` 当且仅当
  `checkpoint_type=active_checkpoint`，并且必须 `lifecycle=open`、
  `outcome=interim`；
- `review_kind=postmortem` 当且仅当 `checkpoint_type=postmortem`，并且必须
  `lifecycle=closed`、`outcome=final`；
- `checkpoint_type=exit` 必须 `lifecycle=closed`、`outcome=final`；
- `open + final`、`closed + interim` 均非法，任何 `final` 都要求 `closed`。

开放持仓的 `active_checkpoint + operation ready + outcome interim` 是正常状态。不得生成
不存在的退出事件、最终 P&L 或最终结论。

## 8. 本地优先、受控市场补齐

固定策略为 `local_first_controlled_fallback_v1`：

1. 先以正式 DB `mode=ro` 检查并装配 cutoff-safe 的 close/daily/minute/factor/instrument
   元数据；
2. 固化 `coverage_before`；只有 `missing`、`stale` 或 `insufficient` 可触发补齐；
3. 只调用仓库/运行环境中已有、精确列入 allowlist 的 adapter/endpoint；
4. 单次 timeout 不超过 20 秒、最多重试 2 次、并发不超过 2、每 run 请求不超过 20；
5. 规范化数据只写新 v3 cache/sidecar；去敏请求、provider/version、真实
   started/completed/fetched 时间、响应状态、request fingerprint、raw/normalized hash
   和 cache lineage 写入 v3 临时回执；
6. 冻结 `coverage_after`、全部可用 supplemental rows，或显式 `missing/failed` projection。

allowlist 必须同时声明
`allowlist_version=market_provider_allowlist.v1` 与
`allowlist_sha256=sha256:1e612c7bf6090fcbfd32aaaef9ca7c73db8441ba939726b9d610238b29b3790a`，
并且恰好等于以下十个代码所有的 `provider:endpoint`，不得缺项、增项或交叉拼接
provider/endpoint：

- `baostock:history_k_data_plus_5m`
- `tushare:adj_factor`
- `tushare:cb_daily`
- `tushare:daily`
- `tushare:etf_basic`
- `tushare:etf_mins`
- `tushare:fund_adj`
- `tushare:fund_daily`
- `tushare:stk_mins`
- `tushare:stock_basic`

每个 endpoint 的 `redacted_parameters` key 也由代码闭合：

| endpoint | 允许的参数 key |
|---|---|
| `baostock:history_k_data_plus_5m` | `code, fields, start_date, end_date, frequency, adjustflag` |
| `tushare:adj_factor`、`tushare:cb_daily`、`tushare:daily`、`tushare:fund_adj`、`tushare:fund_daily` | `ts_code, trade_date, start_date, end_date, fields` |
| `tushare:etf_basic` | `ts_code, fields` |
| `tushare:etf_mins`、`tushare:stk_mins` | `ts_code, freq, start_date, end_date, fields` |
| `tushare:stock_basic` | `exchange, list_status, fields` |

参数 value 也是闭集字符串：先去除首尾空白，每项最长 512 字符，只有 `exchange`
允许空字符串。安全语法精确为：

- `code`：小写 `sh|sz|bj`、点号、六位数字；`ts_code`：六位数字及大写
  `.SH|.SZ|.BJ`；
- `start_date/end_date`：`YYYYMMDD`，或 `YYYY-MM-DD` 后可选
  ` HH:MM:SS`；`trade_date`：`YYYYMMDD` 或 `YYYY-MM-DD`；
- `fields`：一个或多个逗号分隔的 ASCII identifier；
- `exchange`：空值或精确 `SSE|SZSE|BSE`；`list_status`：精确 `L|D|P`；
- baostock 5 分钟 endpoint 只能是 `frequency="5"` 与 `adjustflag="3"`；
  Tushare 分钟 endpoint 只能是 `freq="1min"`。

表外参数和不匹配语法的 value 都拒绝。token、secret、password、API key、credential、
authorization/auth、header、cookie、session、bearer、proxy、access/private key、
signature 等敏感模式会不分大小写地同时检查 key 和 value；安全 key 也不能携带疑似秘密
内容。每个 receipt 必须声明
`request_fingerprint_version=market_request_fingerprint.v1`；`request_fingerprint`
不是调用方自报值，而是从该版本、provider、endpoint、provider version 与按 key 排序的
安全参数规范投影中确定性派生，任何漂移都拒绝。

固定上限对象必须原样为
`timeout_seconds=20`、`max_retries=2`（因此单个 receipt 的 HTTP
`attempt_count<=3`）、`max_concurrency=2`、`max_requests_per_run=20`。
`request_count` 不是逻辑请求条数，而是本 run 的全部 HTTP 尝试数，必须严格等于
`sum(fetch_receipts[*].attempt_count)`。`fetch_receipt_refs` 必须与内嵌 receipt ID
集合精确一致。

fallback `status` 只有四个冻结值：
`not_needed | succeeded | failed | provider_unavailable`；不存在模糊的
`attempted` 或 `not_attempted`。本地 `coverage_before=satisfied` 时必须
`status=not_needed`、
`request_count=0`、非空且冻结的本地 `cache_refs`，且不得出现任何外部 fetch receipt。
fallback `succeeded` 必须至少有一个 `response_status=succeeded` 的 receipt、非空
`cache_refs`，并在成功 receipt 中记录真实 `fetched_at`、raw/normalized SHA-256、
非空 `cache_entry_refs` 和非空 `cache_lineage`；总 `cache_refs` 必须覆盖每个成功
receipt 的 `cache_entry_refs`。成功后 `coverage_after` 可以是 `satisfied`，也可以诚实
保留 `missing/stale/insufficient`。provider 不可用、失败或补齐后
仍不足只降低 market 轴，不阻断 operation facts。执行后获取的数据默认
`reconstructed_public_context`；缺少真实 publication time 时保持 null + `unknown` basis。
不得反推用户实际看过，也不得声称系统在决策时观察。

每个内嵌 receipt，无论成功、失败、rejected、timeout，还是零请求的
`provider_unavailable`，都必须有非空 `cache_lineage`，绑定触发该回退的本地 cache
requirement；该 provenance 不能因未发出 HTTP 请求而省略。

`coverage_after` 与 market 轴必须精确对应：`satisfied -> available`；
`missing -> missing | failed`；`stale -> stale | failed`；
`insufficient -> insufficient | partial | failed`。fallback 的全部 `cache_refs` 必须是
market `source_refs` 的子集；成功 receipt 的全部 `cache_entry_refs` 既必须进入 fallback
`cache_refs`，也必须进入冻结的 market `source_refs`。每个 receipt 的
`started_at/completed_at/fetched_at` 都不得晚于 checkpoint `knowledge_cutoff`。只要存在
成功外部 receipt，market temporal role 就必须为 `reconstructed_public_context`，且
market `fetched_at` 必须等于成功 receipts 中最晚的真实 `fetched_at`。

pre-bundle cache step 之外一律禁止联网。facts renderer、source replay、API 和 UI 的
`network_allowed` 固定为 false。

## 8A. v4 公开时间知识政策（独立 v2）

v4 不重解释上文任何 v1 对象。它新增
`investment_review.operation_checkpoint.v2`、
`local_first_controlled_fallback_v2` 和
`public_availability_user_knowledge_v1`，并保持 v1 schema 文件、canonical bytes、ID、
validator、row-integrity hash 与 replay 不变。

v2 checkpoint 身份在 v1 cutoff 身份之外明确绑定：

- `operation_anchor_event_id`；
- `operation_anchor_at`；
- 四项 P2C canonical `operation_anchor_ordering_key`；
- `perspective`、`as_of`、`knowledge_cutoff`；
- `information_time_policy_version`。

anchor 不接受调用方自报。builder 必须从同一 episode 和已验证 operation review 重算：
entry/adjustment/exit/postmortem 使用对应实质操作；active checkpoint 使用不晚于 `as_of`
的最后一个 selected、validated、material operation，并强制
`operation_anchor_at <= as_of <= knowledge_cutoff`。

每个 v2 market component 都必须保存 closed `information_time`：`status`、
`lower_bound`、`upper_bound`、`basis`、`method_version`、`revision_ref`，并把 exact content
hash/revision/source ref 与 `perspective_eligibility` 绑定。用户视角只有 exact version 的
公开区间已验证且 `upper_bound < operation_anchor_at` 时，才能投影
`user_known_at_operation_by_verified_publication`，并把
`projected_user_known_at` 固定为 anchor。上界等于 anchor 不属于“操作之前”，必须是
ambiguous/ineligible。date-only 时间按来源时区形成整日闭区间，并仍以区间上界比较；未知
时区、冲突时间、无法证明 revision、后续修订借用旧发布时间或操作后公开均不得提升 coverage。

这是可知性政策，不是实际阅读证据。所有输出都保持
`actual_user_observation_proven=false`，不得据此推断用户注意、理解、motive、thesis 或
因果。system 视角只在真实 `system_observed_at <= operation_anchor_at` 时投影
`system_known_at_operation`；公开时间不能替代系统观察。

v2 pre-bundle cache step 可以在当前真实时间获取历史已公开版本。`started_at`、
`fetched_at`、`completed_at`、`system_observed_at` 永远保存真实 audit time，可以晚于
operation 或 historical cutoff，不得回填、截断或拿来冒充 publication time。user 结果不
能仅因晚 fetch 被 withheld；system 请求若不可能改善 operation-time system eligibility，
则使用 `withheld_by_cutoff`，并且严格为零 attempt/零 request、无 fetch/hash/cache entry。
共享预算耗尽使用独立 `budget_exhausted` limitation；以上局部限制都只降低 market 轴，
不得取消 operation-ready active checkpoint。

v2 receipt 额外闭合 `attempt_count_status` 与 `budget_charged_attempts`。provider 裸异常无法
证明精确尝试数时，不把预算上界写成事实：receipt 保存 `attempt_count=0`、
`attempt_count_status=unknown` 和实际保守扣减，fallback 分别保存已验证的 `request_count`、
`request_count_status=bounded_unknown`、`unverified_attempt_upper_bound` 与
`provider_attempt_count_unknown`。零请求 limitation 则使用 verified/zero guard receipt，且
`guard_audit_at=started_at=completed_at`，没有 fetched/system-observed/hash/cache-entry。

checkpoint market 轴必须闭合代表源的 `representative_source_id`、完整 envelope content ID、
`information_time`、`version_provenance`、`perspective_eligibility`，并绑定只含 component/row
sources 的 `market_evidence_manifest_content_id` 以及
`market_evidence_manifest:<content_id>` source ref。外层 temporal role 使用简化词表，详细资格
角色留在嵌套 proof。无代表源时上述五项均为 null，时间均为 null，basis 为
`not_applicable`、role/status 为 `missing`，但空 evidence manifest 仍必须有稳定 content ID。

每个本地 v2 component source 还必须嵌入受限且 canonical 的原始数据库行；每个外部
source 必须嵌入完整、canonical 且不可变的 cache entry。离线 source replay 必须从该
origin proof 重建投影值、effective/public time、version/revision proof、eligibility、
receipt lineage 和 row identity。派生字段、hash 或 ref 不得脱离 origin proof 相互“自证”；
revision conflict 必须由竞争的 origin proofs 派生。provider 返回的 canonical bytes 完全
相同行可确定性去重；bytes 不同的行仍是不同 revision candidate，不得静默合并。

若前一 provider 已有已验证的成功 receipt，后续 provider 出现尝试数未知，bounded fallback
聚合仍保持 `succeeded` 并保留已成功证据，同时新增 bounded-unknown limitation。后续不确定性
不得抹除已成功事实，也不得伪造精确 request total。

v2 继续使用同一份 allowlist、参数语法、去敏、20 秒 timeout、2 次 retry、2 并发、每 run
20 次 attempt、cache lineage 与下游离线边界。raw cache 只有在 bytes、revision 与
information-time provenance 完全相同时才能跨 perspective 复用；requirement、resolution、
manifest、task/run key 必须绑定 perspective/policy/anchor。

存储升级是显式 opt-in 的单次 marker 事务，不是 initializer 行为。只有 exact v1 marker、
固定 v1 manifest、零 WAL、`quick_check=ok`、完整 DDL 与全部 v1 row replay 均通过，才可在
同一 `BEGIN IMMEDIATE` 中把 reviewability/checkpoint/market/manifest marker 更新为 v2，
并新增 public-information marker。升级不得执行 DDL；v2 manifest 的固定 SHA-256 为
`352a9abff69da24e50bc0add0f0dcd802f500463b41cc826f6a140a02f2a4094`。升级后可读取、重放和
幂等跳过既有 v1 row，但不得创建新 v1 row；v2 新 row 必须使用新的明确
`knowledge_cutoff`，先检测底层 v1 unique tuple 冲突，不能原地修订。
升级器还必须在 RW 打开前后及 `BEGIN IMMEDIATE` 锁内重新核对最初 main/WAL/SHM 文件身份、
零 WAL 状态和 SQLite `main` 路径；同内容替换、mtime/content 漂移或锁内身份变化均在 marker
写入前 fail closed。

## 9. 确定性、兼容与安全

- checkpoint 使用 `investment_review.operation_checkpoint.v1`；`checkpoint_key` 固定匹配
  `^review_checkpoint_key_[0-9a-f]{64}$`。根对象、六轴、字段、gap、fallback、receipt
  和 governance 都是闭合对象，未知字段（包括 motive/advice/score）一律拒绝。
- map key 顺序不影响 canonical bytes；只有语义无序的 refs/gaps/allowlist 可排序，交易
  timeline 保持业务顺序。
- binary float 拒绝；Decimal 以字符串保存。canonical payload/content hash 不含
  wall clock/`inserted_at`；独立的
  `investment_review.operation_checkpoint_row.v1` row-integrity hash 则绑定完整投影、
  payload SHA-256 与实际 `inserted_at`，读取时重算，防止合法 UTC 时间或投影被静默篡改。
- 同 checkpoint key 同内容返回 `SKIPPED`；同 key 内容漂移报 conflict；旧记录 create-only。
- schema marker 同时固定 reviewability version、checkpoint contract、market policy、
  allowlist version/hash 与完整 foundation manifest hash；不能只检查表名子集。
- 不修改 core `SCHEMA_VERSION=2`、product-completion v1 marker、旧表 CHECK、event ID、
  Decision 合同、P2C/P2E-3/P2F schema/validator/golden。
- 不允许 motive、thesis、心理/人格诊断、行为 score、数值 confidence、买卖/仓位 advice、
  broker/order、正式 DB 写入、旧 sidecar 写入、模型调用或生产发布。

## 10. 人工展示

API/UI 首屏用自然语言分别说明“操作复盘是否完成”和“哪些局部信息受限”。raw gap code
只在证据抽屉/技术详情中显示。用户可核查 perspective、来源、有效时间、公开/抓取/观察/
录入时间与局部限制。任何 human correction 都是 append-only，并保留 reviewer、reason、
双时间、expected parent 与 supersession lineage。

## 11. 本地只读人工验收入口

工程验收通过后，不要用普通持仓 Dashboard 直接审核复盘产品。普通入口会读取持仓、刷新
行情并允许追加复盘记录；它不等于无副作用的人工验收环境。

从专用 worktree 启动：

```powershell
Set-Location "C:\Projects\03_Investment_System_investment_review_reviewability"
& ".\scripts\start_investment_review_acceptance.ps1"
```

默认只绑定 `http://127.0.0.1:8766/`。启动器逐项验证 exact v3 candidate 的 SHA-256 与
关闭态，显式选择已验收 runner artifact root，跳过 portfolio initializer，关闭 review
automation、provider、盘中/业绩刷新与全部外网，并把候选库锁为
`mode=ro&immutable=1 + query_only`。服务端只开放静态页面、健康身份和 investment-review
GET；portfolio/realtime/refresh 以及 decision/link/fee/review correction 均返回
`review_acceptance_read_only`。

停止时只使用任务自带的精确身份停止器：

```powershell
& ".\scripts\stop_investment_review_acceptance.ps1"
```

停止器核对任务 ID、PID、可执行文件、启动时间、命令行、候选指纹与端口健康身份；任何一项
不匹配都拒绝终止进程。它不猜测、不复用也不终止未知端口占用者。

人工至少查看一组 single user/system、一组 weekly、一组 monthly、一个
`decision=not_recorded`、一个 missing-not-zero 字段、一个已验证发布时间早于操作但抓取较晚的
对照，以及一个包含 owner/next step 的证据缺口。工程 smoke、截图或自动 DOM 断言都不能把
`human_product_acceptance` 从 `pending` 改为 `accept`。用户最终只返回
`accept`、`accept_with_issues` 或 `reject`，并以当时的 exact Git HEAD 为准。
