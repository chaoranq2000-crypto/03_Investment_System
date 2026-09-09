# 旧试点工具退役与历史审计提速

状态：代码退役、依赖解耦、文件隔离、恢复验证、全套回归及用户手动物理删除均已完成。

## 范围与恢复依据

本轮按用户“为我执行下一轮的瘦身清理”执行，沿用单一待删文件夹交付方式。清理前提交为 `66f5884b3eeef779b69dde8c3b28524fd66ec31e`，工作树为 `C:/Users/Q/.codex/worktrees/slim20260906/03_Investment_System`。

共移出 22 个旧文件，原始内容与 Git 内容均为 91,391 bytes（约 89.25 KiB）。19 个属于旧试点、readiness、promotion、补丁清单及固定 readout 工具，另 3 个为 Bundle 11 聚合包装、独立 CLI 测试及重复 CI。每项保留固定提交、Git blob、字节数、SHA-256 和现存引用依据。本轮新增一份通用历史读取测试和本记录，受管理文件净减少 20 个。

当前指针、研究运行、原始证据、已审核输入、共享研究门、Portfolio、Investment Review、人审契约及正式账本不在修改范围内。保留 476 条既有退役路径和 78 条用户已删除的完整恢复记录；本轮 22 条最初进入 `manual_delete_candidates`，用户删除并核验后转入已完成记录。当前待删队列为空，完成索引共 100 条。

## 实现边界

旧四个试点 CLI 随专用配置与回归退役；格式检查只解除两个已退役 CLI 的文件存在性及 `--help` 要求。当前 research pack 契约、工作流状态验证及报告降级、TODO 和无直接投资建议检查继续保留。旧 reviewed-input renderer 直接退役，没有将它的文本启发式检查悄悄迁入当前 writer。

Bundle 11 保留 `scripts/run_r5_bundle11r_runtime.py`、`config/r5_bundle11r_runtime_contract.yaml` 和六个功能组件。原聚合函数合入现存 CLI，原有调用参数、配置默认值、输出结构与退出码保持一致。原唯一 CLI 回归移入 engine 测试，并覆盖真实命令在 ready/gap 两种情况下的 YAML、JSON、stdout 和 0/2 退出码。主 CI 继续执行默认测试全套及受管理 Python 编译检查，覆盖保留的三份 Bundle 11 测试文件；移除专门 CI 会减少一次独立的快速反馈任务。

`tests/conftest.py` 统一按固定 40 位提交与字面路径批量读取历史 Git 对象，校验提交身份、对象类型、长度、Git OID 和 SHA-256。缓存只复用不可变对象；损坏批次不留下部分缓存。历史 cleanup、baseline 与 blocker 检查保留原测试项目、哈希与语义断言，共享字节及文本索引。当前物理路由扫描保留，并核验 blocker reader 对共享 helper 的真实委托。

## 验证记录

详细证据目录：`.codex_tmp/legacy_pilot_history_slimming_20260907/`。

| 检查 | 结果 |
|---|---|
| 移出前九份旧工具测试 | 29 passed，1.12 秒 |
| 同组历史审计改造前／后 | 33 passed / 33 passed；190.70 秒 / 6.42 秒，耗时减少约 96.6% |
| 新批量 reader 边界与失败用例 | 26 passed |
| Bundle 11 等价核验 | main、run_runtime、write_yaml 三函数 AST 一致；七份输入哈希不变；ready/gap 完整输出一致 |
| 清理前当前研究离线重放 | 17 个产物，byte drift 0，无网络访问、无历史运行目录读取 |
| 移动与恢复核验 | 22 个原路径均已移出，隔离副本 SHA-256 全部一致；待删目录共 24 个文件，含 README 和收据 |
| 当前功能、契约与共享能力回归 | 79 passed；路由保护 17 passed；429 个受管理 Python 文件编译通过 |
| Research smoke | 8 步全部通过，包含当前状态、来源路由、保护检查及研究包契约 |
| 默认全套 | 2234 passed、2 skipped、59 deselected；561.96 秒 |
| 历史兼容全套 | 59 passed、2236 deselected；30.82 秒 |
| 最后一次路由 guard 补强后的定向复验 | 路由、通用 reader 与退役清单共 59 passed、1 deselected；14.49 秒 |
| 当前研究产物前后比较 | 17 个产物 SHA-256 全部一致；未新增正式运行或改变指针 |

上述 96.6% 只对应同组 33 项历史审计，不等于整个默认测试套件的提速比例。

独立审查确认三份历史审计的原有 309 条 assert AST 逐条一致。完整回归之后，仅补强测试 guard 对 `open(...).read()` 物理回退的拒绝并加入对应负例，运行代码未再变更；随后执行表中最终 59 项定向复验，独立复核也确认该漏洞关闭。默认全套结果属于补强前的测试代码快照，最终 guard 的验证以定向复验为准。

保护审计确认：除本轮授权更新的退役清单外，其他保护路径没有变更；清单的保护范围、不变量、历史快照、476 条旧退役路径及 78 条已完成记录逐项保持不变。精确暂存范围为 34 个路径，证明见证据目录中的 `final_scope_and_quarantine_audit.json`。

## 精确移出清单

```text
.github/workflows/r5_bundle11r_runtime.yml
config/r5_next_pilot_gate_rules.yaml
config/r5_pack_promotion_rules.yaml
config/r5_readiness_gate_rules.yaml
config/r5_reviewed_input_pilot_gate_rules.yaml
scripts/check_r5_task_readout_sync.py
scripts/r5_next_pilot_gate.py
scripts/r5_pack_promotion_gate.py
scripts/r5_patch_inventory_check.py
scripts/r5_readiness_gate.py
scripts/r5_reviewed_input_pilot_gate.py
scripts/render_r5_reviewed_input_output.py
src/research/r5_bundle11r_runtime.py
tests/test_r5_bundle11r_runtime_cli.py
tests/test_r5_next_pilot_gate.py
tests/test_r5_next_pilot_gate_after_registries.py
tests/test_r5_pack_promotion_gate.py
tests/test_r5_patch_inventory_check.py
tests/test_r5_pilot_gate_recheck_and_render.py
tests/test_r5_readiness_gate.py
tests/test_r5_reviewed_input_pilot_gate.py
tests/test_r5_task_readout_sync.py
```

## 用户删除核验（2026-09-07）

用户反馈“已删除”后，现场逐项核验本轮 22 个原路径和 22 个隔离副本均不存在。独立核验也确认全部 22 条仍可从固定提交 `66f5884b3eeef779b69dde8c3b28524fd66ec31e` 恢复，Git blob 类型、OID、长度及 SHA-256 全部一致，共 91,391 bytes。

本轮 22 条记录已转入 `completed_manual_deletions`，登记 `deletion_actor=user`、核验日期和本记录路径。原有 78 条完成记录及清单其他字段逐项不变；`manual_delete_candidates` 为 0，完成索引为 100。删除证据另存 `.codex_tmp/legacy_pilot_history_slimming_20260907/user_deletion_verification.json`，原移动收据作为历史证据保留。

本次仅更新清单与删除记录，没有改动运行代码、测试代码或业务数据；此前完整回归结果仍适用于代码版本。收尾验证：Doc drift 通过，清单、路由及历史保护回归 34 passed（19.78 秒）；100 条完成记录的 Git 恢复完整性检查通过。

## 剩余事项

原待删目录：`C:/Users/Q/.codex/worktrees/slim20260906/03_Investment_System/.codex_tmp/manual_delete_legacy_pilot_history_20260907/`。22 个旧文件已由用户物理删除；目录中仅剩 `README.md` 和 `cleanup_manifest.json` 两份辅助记录，可保留或由用户手动删除。外部证据目录另有收据副本。Codex 没有执行删除命令。

本轮遵循 `AGENTS.md` 的文件删除规则：“Do not remove directories automatically. If the requested scope contains multiple files or any directory, stop and ask the user to perform the deletion manually.” 上述删除及索引更新已完成核验。

本轮仅保存本地提交，未推送或合并。恢复提交包含前序本地提交；后续发布需保留其可达性，不应只复制最终文件或丢弃恢复历史。

| 剩余事项 | owner | severity | 下一步 |
|---|---|---|---|
| 瘦身分支发布 | user | medium | 确认发布范围后推送或合入主线，并保留恢复提交 |
