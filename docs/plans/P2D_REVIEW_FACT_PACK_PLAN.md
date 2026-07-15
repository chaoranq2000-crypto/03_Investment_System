# P2D Review Fact Pack：实施计划

基线：`codex/portfolio-tracker@8d1623420f0a9118357fbc0436a456690f4cf6c4`

## 目的

在 P2B 审计快照与 P2C 交易周期事实之上增加一个低耦合、确定性、可验证的 read model，使后续 UI、查询和 AI 复盘共享同一事实边界。

## 本补丁范围

- 新增 `src.investment_review.review_pack`；
- 新增独立脚本入口；
- 新增 P2D playbook；
- 新增确定性、provenance、未解决链接和篡改检测测试；
- 不修改 P2B/P2C 数据库、schema 或构建器；
- 不修改现有 `src.investment_review.__main__`，降低与本地未提交改动冲突。

## 合并步骤

1. 在干净工作树检出基线 SHA；
2. 执行补丁包的 preflight；
3. `git apply --check p2d_review_fact_pack.patch`；
4. `git apply p2d_review_fact_pack.patch`；
5. 运行目标测试；
6. 用一份脱敏 P2C artifact 双构建并比较目录；
7. 运行 `validate --episodes ...`；
8. 人工检查一个 closed episode、一个 open episode、一个含 unresolved 链接的 episode；
9. 单独提交，建议提交说明：`feat(review): build auditable episode fact packs`。

## 验证命令

```powershell
.\.conda\investment-system\python.exe -m pytest tests/test_investment_review_p2d_review_pack.py -q

.\.conda\investment-system\python.exe -m src.investment_review.review_pack build `
  --episodes data/processed/normalized/trade_episodes.local.json `
  --output-dir data/processed/review_fact_packs/run_a

.\.conda\investment-system\python.exe -m src.investment_review.review_pack build `
  --episodes data/processed/normalized/trade_episodes.local.json `
  --output-dir data/processed/review_fact_packs/run_b

# Windows PowerShell 目录哈希可逐文件比较；Linux/macOS 可用 diff -qr。

.\.conda\investment-system\python.exe -m src.investment_review.review_pack validate `
  --bundle-dir data/processed/review_fact_packs/run_a `
  --episodes data/processed/normalized/trade_episodes.local.json
```

## Gate

通过：

- 目标测试全部通过；
- 双构建字节一致；
- unresolved 状态数量与 P2C 源 episode 一致；
- 绝对本地路径没有进入 artifact；
- 事实包没有新增解释性结论。

暂停并回流：

- P2C 根结构与当前兼容面不匹配；
- episode id 在真实数据中并不稳定；
- 时间字段存在多时区或非 ISO 口径且排序会改变事实语义；
- `missing/unlinked/ambiguous/invalid` 不是字符串 status，而是另有 canonical schema；
- 现有 CLI 已有同名 P2D 能力。

## 后续迭代

### P2D.1：与现有总 CLI 对接

在确认 `src.investment_review.__main__` 的 argparse 契约后，把 `review-pack-build` 与 `review-pack-validate` 接入总入口；这一修改应单独提交，避免本补丁与本地未提交 CLI 改动冲突。

### P2D.2：事实包查询层

增加按 symbol、日期、状态、unresolved 类型查询的只读接口；查询结果只返回 bundle id 与 source pointer。

### P2E：复盘编排

引入 `fact / interpretation / alternative / unknown` 四类 statement，所有 fact 必须引用 P2D pointer；AI 不得补齐 missing links。
