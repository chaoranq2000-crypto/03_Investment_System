# P2F 全阶段 Task Card：单笔交易双视角复盘闭环

## 基线与依赖

- Repo: `chaoranq2000-crypto/03_Investment_System`
- Branch: `codex/portfolio-tracker`
- Planning base: `fa6680c8b5e6cfe23a03cc95b6c77800a3d27650`
- Production base: P2E-3 final release commit（待实现后固定）
- Delivery model: one external patch package / five internal commits

## 阶段目标

消费 P2C Trade Episode、P2E-3 组合上下文以及可选 Decision/市场/结果来源，产出可追溯、可修订、事实与解释分离的 `p2f.episode_review.v1` artifact。

## 必须实现

- deterministic review input bundle；
- 双时间与 future-information isolation；
- facts-only review；
- source refs 与 availability；
- main tension / hypothesis / alternative explanation；
- retrospective counterfactual options（非建议）；
- no-advice/no-score policy；
- model/prompt/output provenance；
- facts-only fallback；
- human correction 与 append-only revisions；
- JSON/Markdown render；
- validate/show/diff/revision-list 或等价入口；
- 至少 64 个定向用例（P2F-1/2/3/4/5 分别不少于 14/16/14/12/8）；
- clean checkout、CI、补丁包与 SHA256。

## 禁止实现

- 不复制 P2E-2/P2E-3 公式或上下文构建逻辑；
- 不用结果直接判定决策好坏；
- 不将未知值写成 0；
- 不生成直接买卖/持有/仓位建议；
- 不进行心理诊断；
- 不覆盖旧修订；
- 不回写源交易数据库；
- 不在 P2E-3 未完成时宣称 P2F 完整发布。

## 内部提交

1. P2F-1 deterministic inputs
2. P2F-2 facts-only review
3. P2F-3 bounded interpretation
4. P2F-4 corrections and rendering
5. P2F-5 hardening and release

## 验收命令

按真实仓库环境映射后，至少运行：

```powershell
python -m compileall -q .
python -m pytest -q <P2F targeted tests>
python -m pytest -q
```

随后在干净检出重复全仓测试，并等待远端 CI 成功。
