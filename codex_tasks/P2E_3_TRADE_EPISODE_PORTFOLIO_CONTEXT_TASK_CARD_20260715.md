# P2E-3 Task Card：Trade Episode Portfolio Context

## 基线

- Repo: `chaoranq2000-crypto/03_Investment_System`
- Branch: `codex/portfolio-tracker`
- Expected base: `fa6680c8b5e6cfe23a03cc95b6c77800a3d27650`
- Patch class: Stage-2 fact-layer integration

## 目标

把 P2E-2 可追溯组合指标绑定到 P2C `Trade Episode` 的关键操作锚点，输出确定性、双时间、只读、可修订的 `trade_episode_portfolio_context` artifact。

## 必须实现

- episode open/change/close 的 pre/post 锚点；
- `as_of` + `knowledge_cutoff`；
- P2E-2 metric registry 复用；
- Decimal 字符串；
- method/source provenance；
- missing/ambiguous/stale/unpriced/invalid warnings；
- 兼容指标的 pre/post delta；
- canonical JSON + stable content ID；
- 同秒稳定排序和不确定性降级；
- atomic write；
- 源数据库只读；
- validate/show CLI 或现有等价入口；
- playbook 和定向测试。

## 禁止实现

- 不复制 P2E-2 指标公式；
- 不把未知值写成 0；
- 不使用事后价格/分类/修订；
- 不依赖 SQLite 隐式顺序或 rowid；
- 不输出行为诊断、评分、建议或自然语言结论；
- 不修改用户现有脏工作区内容；
- 不直接推送或创建 PR，除非另行明确要求。

## 首要回归点

对同一秒内的现金快照、成交和修订建立明确 tie-break；信息不足时返回 `ambiguous`。测试必须循环或重排插入顺序，证明结果不受物理顺序影响。

## 验收命令

按仓库现有环境执行，至少包括：

```powershell
python -m compileall -q .
python -m pytest -q <P2E-3 targeted tests>
python -m pytest -q
```

随后在干净检出中重复全仓测试，并等待远端 CI 成功。

## 交付物

- 实现提交；
- 定向测试与全仓结果；
- CI 链接；
- `base..target` 补丁 ZIP；
- manifest（base SHA、target SHA、测试、文件列表）；
- SHA256；
- 已知限制与后续阶段建议。
