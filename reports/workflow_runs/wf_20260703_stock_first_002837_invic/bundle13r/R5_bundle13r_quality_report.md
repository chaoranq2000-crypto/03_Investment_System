# R5 Bundle 13R 质量复核报告

## 结论

Bundle 13R 的实现与执行链可按允许状态 `R5_BUNDLE13R_BACKFLOW_IN_PROGRESS` 技术关闭；经营证据资格仍为 `needs_fix`。严格运行得到 `6 resolved / 11 unresolved / 0 validation blockers`，不存在无效 reviewed-backfill，但四项 high 研究缺口阻止 12R 重跑、估值资格刷新、Reader 和 P2。

## 非补偿检查

| gate / local check | result | evidence or limitation |
|---|---|---|
| G0 / `QR-B13R-BASELINE` | pass | canonical generation `op_evidence_gen_r5_bundle12r_fd5d23c5eb35ac27` 与四个物理哈希通过 `baseline_audit.yaml`；原包错误绑定保留为历史失败证据。 |
| G1 Evidence Gate | pass | 2025A 年报、业绩说明会、2026-07-15 SZSE 与 CNINFO IR live receipt 均有 evidence ID、raw/normalized 路径；manifest/path/candidate validation 通过。 |
| G2 Claim Gate | pass | 年报分部值为 fact；液冷约 3 亿元保持 2024A `management_comment / bounded_estimate`；重叠关系明确标为审阅后 inference。 |
| G3 Metric Gate | needs_fix | 公司收入和毛利分母、三项独立暴露均含 period/unit/source/method；九个经营驱动仍为 `missing`，未被公司级代理补齐。 |
| G6 Exposure Gate | needs_fix | room/cabinet 为 disjoint；两组 liquid 横切关系为 overlaps，但收入与毛利扣减均缺失，禁止加总。 |
| G8 Backflow Gate | pass | 决策、resolved/unresolved 列表、owner、替换触发器及下一 skill 均显式；workflow state 与 generation lock 同步。 |
| G9 No Advice Gate | pass | 无 buy/sell/hold、目标价、仓位或确定收益表达；`sample_quality_allowed=false`、`p2_allowed=false`。 |
| `QR-B13R-LOCK` | pass | generation `backflow_gen_r5_bundle13r_fb8cefccfaa93293` 的 lock 校验通过；同输入二次运行 8 个锁定/输入工件 hash drift 为 0。 |
| `QR-B13R-DOWNSTREAM` | pass_closed | 决策未达到 `ready_for_bundle12r_rerun`，因此未执行 12R 重跑；估值前置条件也未触发。 |
| `QR-B13R-REGRESSION` | pass | 13R 聚焦 `19 passed`；历史状态兼容修复集 `20 passed`；最终全仓 `773 passed, 2 skipped`。 |
| `QR-B13R-STATIC` | pass | 7 个相关 Python 文件完成无落盘 AST compile；12 个 bundle13r YAML 可解析；4 行质量 issue schema/enum 校验通过；doc drift 与 `git diff --check` 通过。 |

## Issue 结果

- open critical: `0`
- open high: `4`
- resolved preflight critical: `2`
- outcome: `needs_fix`
- technical close state: `R5_BUNDLE13R_BACKFLOW_IN_PROGRESS`

四项 high issue 分别覆盖两组经营驱动缺口和两组 overlap 数值扣减缺口。它们是公开、可路由的研究缺口，不是 schema 或执行错误。

## 人审与下游边界

`human_review_status=pending` 是 Bundle 13R 固定边界，不继承 Bundle 11R 的精确哈希人审。当前没有新 Reader，因此不创建或伪造 Reader 人审通过状态；peer、DCF、SOTP 均沿用 12R 的关闭结论，等待经营证据真实 requalified 后再独立复核。
