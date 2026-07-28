# 周期投资复盘读者版 V2 本地候选（验证通过）

- P1 用户授权：`accept_p1_sample_and_continue`（已记录）
- P5 用户授权：`accept_reader_report_samples_and_continue`（已记录）
- 六类真实报告：6 / 6
- 派生报告库当前报告数：619
- 正式组合库 SHA-256：`6207d15cc61cffd963cc8154a1b9af2ddae56ae11efe9a26116f7792e6ffb057`（前后不变）
- 默认主文：中心判断、综合分析、操作复盘与行动；完整事实默认折叠
- 运行时模型/provider：未接入；V1 历史报告保持兼容
- 订单执行：`false`；券商访问：`false`；保证收益：`false`
- 生产发布：`false`；OS scheduler/service：未安装

## 最终验证

- V-101：110 项后端周期报告、动机、建议、runner、API 与端到端测试通过。
- V-102：23 项前端测试通过；Vite 生产构建通过并更新 `web_assets`。
- V-501：71 项自动化、API 与 Web 测试通过。
- V-601：用户授权 `accept_reader_report_samples_and_continue` 已记录。
- V-701：5 项新增叙事专项测试通过；与 V-101 合计 115 项受影响测试通过；V1 兼容和确定性 V2 fallback 通过。收口复核另运行 5 项编辑回归，已消除 `MISSING等因素` 这类机械表达，同时在结构化事实中保留缺失状态。
- V-702：localhost 只读验收通过。V2 默认显示中心判断、综合分析、行动与风险；完整事实附录默认折叠且可展开；V1 旧报告回退正常；浏览器控制台 0 error / 0 warning。
- V-801：六类真实 V2 报告全部 `accepted`；周/月均有跨日综合；六份重复保存均 `skipped`，sidecar 报告数保持 619、SHA-256 保持 `76de62c9740dc87ca994dcb81a8242d73c22521f436d352978abb09fab34cc76`。
- `compileall`、任务包 validator 与 `git diff --check` 通过。
- 正式组合库 SHA-256 前后均为 `6207d15cc61cffd963cc8154a1b9af2ddae56ae11efe9a26116f7792e6ffb057`。

## 六类样本

- 组合账户 · daily · 2026-07-15 至 2026-07-15 · `periodic_f4d948bbd24570e0b2149ab200c718cd`
- 德展健康 · daily · 2026-07-15 至 2026-07-15 · `periodic_899f2428a2dcc1b172113fc6ef72167f`
- 组合账户 · weekly · 2026-06-29 至 2026-07-03 · `periodic_d8f5c799ed4d76e3c9f5ef651d99ab95`
- 德展健康 · weekly · 2026-06-29 至 2026-07-03 · `periodic_bcd4f7d2d0a3af230d9b5599ea22dfe8`
- 组合账户 · monthly · 2026-06-01 至 2026-06-30 · `periodic_1695124c2ad446827350839c6c2a0376`
- 德展健康 · monthly · 2026-06-01 至 2026-06-30 · `periodic_e8c73040d23d55c55c882da4b6a53bbd`

## 已知限制

- 2026-07-14 以前没有可靠现金快照；相关周/月报告保留总资产 MISSING，并明确改用不含现金的持仓市值变化口径。
- 批量历史日报默认使用正式库本地行情回退；基本面、基准或板块缺失时明确显示，不用未来信息补造。
- 没有显式用户风险预算，精确仓位建议保持为区间。

## 发布边界

- 本地候选已完成；P7 checkpoint 是包含本文件的提交。
- 未 push、未 merge、未 deploy、未安装系统调度或服务、未访问券商、未执行任何报告建议。
