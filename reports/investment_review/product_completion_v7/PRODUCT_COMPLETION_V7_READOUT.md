# Investment Review Product Completion v7

## 结论

v7 已完成并通过合同验收。候选库从已验证的 exact-v2 状态继续，没有重跑 marker、doctor、sync 或已接受的 single user/system；weekly/monthly 两种范围、user/system 两种视角均完成 apply/repeat，重复结果 canonical byte-identical。受保护数据库保持逐字节一致，未发布。

## 冻结依据与检查点

- 冻结合同：`docs/codex_tasks/investment_review_product_completion_v7/CONTRACT.md`
- 合同 SHA-256：`83284cc306ae5a58e0281b048e860bc4822c4a7b6d57ac0270486f0ee938d497`
- source baseline：`aa8e3ed41a957fe6ab891f2a65753294b360d83d`
- v7 setup commit：`ccc69cc`
- v7 P1 commit：`04aed2c`
- v7 P2 checkpoint：本文件所在的 `test(review): close reviewability corrections v7 candidate` 本地提交
- v7 入口候选主库：5,627,904 bytes，SHA-256 `ffb7e377eb1e78e4bb72ff9df71d5f9b45021d6d666d835faf07baba630bd5cd`
- 失败前序证据均保留，未覆盖 v5/v6 证据。

## 授权范围内的修正

1. truthful partial：`partial + missing` 的真实组件组合不再被错误拒绝，缺失组件仍保持 missing。
2. 时间语义：v2 current-industry 不再把 review `as_of` 冒充市场信息的 `effective_at`；保留真实 observation time、`point_in_time=false` 和 unknown eligibility。
3. 旧缓存恢复：只对窄匹配的 legacy current-industry canonical drift 写入版本化 `v2/r_repair` create-only 修复；旧缓存不改不删，任意无效缓存仍 fail closed。
4. API/UI 可审查性：scope 在可信目录读取前下推；同一请求内复用已经完成哈希、路径、内容校验的 receipt，避免真实规模列表重复读取几十次。每个 episode 的 context/input/review/checkpoint 仍逐件校验。

## 真实恢复与幂等性

| 范围/视角 | Episodes | Apply/Repeat SHA-256 | 结果 |
|---|---:|---|---|
| weekly:user | 22 | `481c0bcc6cca5952a84d048c1ee2f7d2108e74ae67c241c09249a082974da9ee` | canonical byte-identical |
| weekly:system | 22 | `8ad2ef78002378a432ea1140e7eb726a3629b19330e6432d9f1ee1d3175b8aae` | canonical byte-identical |
| monthly:user | 25 | `010157904972fe8486f403d431c8b0d90988d3fced5818c9913d9c9f8f57d528` | canonical byte-identical |
| monthly:system | 25 | `81600a7cbc9891470d74c37b41d1ab8d4c758c97e34110aeca1b3a07133f44c6` | canonical byte-identical |

P2 摘要 SHA-256 为 `5fdd79a2dd66779a2cc711eb970594413fd9308a6af0eede85eafee0a6356a1f`。改变只发生在授权的 `review_runs`、`review_run_status_events`、`operation_review_checkpoints`、`operation_checkpoint_gaps`；marker 重跑次数为 0，已接受 single 重跑次数为 0，外网调用为 0。

## API 与浏览器验收

localhost API smoke 通过，single 列表返回两条 paired perspective 复盘。浏览器实际验证了：

- 中文“持仓账本 / 交易复盘”首屏；
- healthy 状态和 single/weekly 范围筛选；
- user/system 双视角；
- 操作事实、决策记录、持仓现金估值、市场信息、持仓回合、结果成熟度六轴；
- 价格、净资产、权重、行业以“缺失 · missing”呈现，不补零；
- 证据抽屉展示 checkpoint、source refs、gap owner/severity/next step；
- `actual_user_observation_proven=false`，没有把公开可得性伪装成实际阅读。

## 数据、缓存与 Windows 关闭态

- 最终候选主库：7,626,752 bytes，SHA-256 `acf3b9c567cbe69ca4536285f4b5027016dd2e0ee2d382ebc4d993ff83410f38`
- `quick_check=ok`，`user_version=2`，checkpoint count=30，target tuple count=2
- 最终 WAL/SHM 均不存在。删除前是 exact 0-byte WAL 与配对 32,768-byte SHM；写进程关闭后按 AGENTS.md 分别删除两个明确文件。
- 删除前/后审计：`.codex_tmp/investment_review_product_completion_v7/p2_recovery/candidate_aux_deletion_before_final.json` 与 `candidate_aux_deletion_after_final.json`
- cache：入口 15，最终 153，新建 138；入口 15 项全部不变，未删除任何 cache。
- formal portfolio DB、用户既有 review sidecar、v2 candidate sidecar 均与 v7 preflight 完全一致。

## 验证

| Gate | 结果 |
|---|---|
| V-101 | 268 passed |
| V-701 | 128 passed |
| V-702 | 19 passed；Vite build passed |
| V-703 | 18 passed |
| V-801 | weekly/monthly apply/repeat、API/browser、network/table/cache/deletion audit accepted |
| V-901 | 1905 passed，2 skipped |
| V-999 | package、protected-source、scope、diff、status、no-lockfile、publication boundary 全部通过 |

## 保留边界

- 这不是买入、卖出、持有或仓位建议。
- 没有推断投资动机、心理或未记录的人类决策。
- `actual_user_observation_proven=false`。
- `human_product_acceptance=false`。
- `production_released=false`。
- 未 push、未建 PR、未 merge、未 tag、未 release、未 deploy；任何发布仍需独立授权。
