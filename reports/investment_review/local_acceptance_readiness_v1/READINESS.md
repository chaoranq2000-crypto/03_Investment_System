# 投资复盘本地只读人工验收说明

## 当前结论

本地人工验收入口已经达到工程就绪状态。它使用 exact v3 候选库和已验收复盘产物，只绑定
`127.0.0.1:8766`，不初始化正式持仓库，不启动自动复盘，不调用行情 provider，不访问外网，
也不允许提交决策、关联、费用纠正或复盘修订。

以下状态必须分开理解：

| 项目 | 当前值 |
|---|---|
| `engineering_acceptance_readiness` | `true` |
| `human_product_acceptance` | `pending` |
| `actual_user_observation_proven` | `false` |
| `production_released` | `false` |

工程测试和浏览器自动检查只能证明页面可安全展示，不能替代您本人对内容是否易懂、是否有用的
判断，也不能证明您在历史操作时实际阅读过某条公开信息。

## 打开与停止

从专用 worktree 启动：

```powershell
Set-Location "C:\Projects\03_Investment_System_investment_review_reviewability"
& ".\scripts\start_investment_review_acceptance.ps1"
```

启动器会先完整校验并预热 96 条复盘，再打开或交付页面。当前机器实测预热约 96 秒；等待完成
后，单个详情实测约 0.8 秒打开。地址固定为：

```text
http://127.0.0.1:8766/
```

停止时只使用：

```powershell
& ".\scripts\stop_investment_review_acceptance.ps1"
```

停止器只会终止清单中记录且 PID、可执行文件、启动时间、命令行、候选指纹、端口和健康身份
全部匹配的进程；它不会猜测或终止未知进程。

## 建议您实际查看的内容

1. 在 `588200.SH` 中分别打开 single 的“用户视角”和“系统视角”，比较市场信息资格。
2. 再各看一条 weekly 和 monthly，确认三个时间范围的含义直观。
3. 查看六个独立状态轴：操作事实、决策记录、持仓/现金/估值、市场信息、持仓回合、结果成熟度。
4. 确认价格、净资产、权重、行业等缺失项显示为“缺失”，没有被补成零。
5. 打开“证据与来源”，检查 gap code、owner、next step 和 source refs 是否足够追溯。
6. 核对“公开时间早于操作、抓取时间晚于操作”的用户视角规则；这只代表政策上可知，
   页面仍明确显示 `actual_user_observation_proven=false`。
7. 确认页面没有决策、费用或复盘修订表单，没有买卖/仓位建议，也没有推断未记录的投资动机。

完成后，请针对交接时的 exact Git HEAD 返回以下三种结果之一：

- `accept`
- `accept_with_issues`，并列出问题
- `reject`，并说明阻断原因

## 已验证结果

- API：96 条复盘；single/weekly/monthly 均同时存在 user/system 视角；六轴字段完整。
- 安全边界：持仓、实时持仓、业绩刷新及四个复盘写接口共 7 个 smoke 路由全部返回
  `403 review_acceptance_read_only`。
- 浏览器：只显示复盘主体；29 个页面资源全部来自 `127.0.0.1:8766`；外部资源和被禁产品接口
  计数均为 0。
- 性能：完整预热约 95.8 秒；已预热的 6 个目标详情均在 0.81 秒内完成。
- 测试：相关后端回归 `89 passed`；前端 `21 passed` 并完成生产构建；全量仓库测试
  `1911 passed, 2 skipped`。
- 数据保护：四个数据库主文件哈希与入口一致；formal/v3 WAL/SHM 不存在；用户旧侧车和 v2
  的既有安全辅助文件保持原样；760 个复盘产物和 153 个市场缓存文件的树清单一致。

主要证据：

- `.codex_tmp/investment_review_local_acceptance_readiness_v1/api_smoke.json`
- `.codex_tmp/investment_review_local_acceptance_readiness_v1/browser/dom_assertions.json`
- `.codex_tmp/investment_review_local_acceptance_readiness_v1/browser/request_trace.json`
- `.codex_tmp/investment_review_local_acceptance_readiness_v1/browser/screenshot_manifest.json`
- `.codex_tmp/investment_review_local_acceptance_readiness_v1/protected_exit.json`

浏览器控制客户端曾在控制面输出两次 Statsig 遥测超时日志；它们不是验收页面或产品运行时发起
的请求，也未出现在页面资产清单中。页面本身与产品进程的外部请求计数均为 0。

## 演练中修复的问题

第一次真实演练发现三项 Windows/产品问题：隐藏属性被旧样式覆盖、详情重复做重型校验、
嵌套 receipt 校验没有继承 immutable 读取，以及停止器对 PowerShell JSON 日期和进程退出
竞态处理不兼容。它们均已回修并重新完成真实演练。

第一次进程产生的候选 WAL/SHM 已先记录主库/辅助文件哈希、大小、进程关闭和独占句柄证明，
再按逐文件权限分别移除。主库从始至终保持 exact SHA-256
`acf3b9c567cbe69ca4536285f4b5027016dd2e0ee2d382ebc4d993ff83410f38`。回修后的完整启动、
浏览器访问和正常停止全过程均未再产生候选 WAL/SHM。

## 仍然不是本阶段完成的事项

- 您本人尚未签收产品体验。
- 复盘中的历史缺失、证据 gap 和 `decision=not_recorded` 没有被伪造填补。
- 没有进行任何人工写入表单测试；如需测试写入，必须另建可丢弃沙箱阶段。
- 没有 push、PR、merge、部署、计划任务或生产发布。
