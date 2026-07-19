# Investment Review Behavior Hypothesis Ledger 操作手册

Behavior Hypothesis Ledger 位于 P2G-4 人工修订之后、P2G-5 发布门禁之前。它是
artifact-only 的可追溯台账，不是新的 canonical 阶段编号，不应称为 `P2G-5`。
路线图中的 P2G-5 仍保留给独立的端到端发布门禁与月度报告能力；本台账不会提前占用
该编号，也不会启动阶段四干预运行时。

## 边界

- 只消费显式传入的完整 P2G-4 revision chains 和精确 P2G-2 observation artifacts。
- 每条 chain 必须从 revision 1 连续到唯一 latest head，并逐 revision 通过 P2G-4
  离线验证；latest head 必须通过 source replay。
- 不读取数据库、网络、模型、当前时间、环境变量或 `latest` 文件别名。
- 不做语义合并、聚类、排名、评分、置信度计算、心理画像或交易建议。
- 查询只做确定性过滤，不产生新解释。

规范 schema：

```text
docs/contracts/P2G_BEHAVIOR_HYPOTHESIS_LEDGER.schema.json
```

## Active 与 Audit

- `accepted` occurrence 可进入 active view。
- `proposed`、`rejected` 和 `superseded` occurrence 只在 audit view 可见。
- 同一 fingerprint 在不同 chain 中同时出现 accepted/rejected 时，active query 只返回
  accepted occurrences；rejected occurrence 不会伪装为 active。
- active view 为空、audit view 非空是合法状态。

## Exact canonical dedup

fingerprint 只由以下完整、规范化业务内容派生：

- statement、scope（含 episode IDs、时间和 market contexts）；
- supporting/counterevidence evaluation refs、supporting reasons 和 search note；
- alternative explanations、assumptions、uncertainty、falsification 和 next observations；
- temporal perspective、warning codes 和 guardrail flags。

只有 fingerprint 完全相同才合并为一个 ledger entry。不同 scope、market context、
evaluation refs、temporal perspective 或任一其他业务字段都不得合并。合并只折叠相同
payload；每个 source occurrence、revision chain、hypothesis ID、status、review history
和 lineage 仍完整保留。

## 构建

必须显式提供每条 chain 的所有 revision；顺序不影响输出：

```powershell
python -m src.investment_review behavior-hypothesis-ledger-build `
  --revision <chain-a-rev1.json> `
  --revision <chain-a-rev2.json> `
  --revision <chain-b-rev1.json> `
  --observation-artifact <p2g2-observations.json> `
  --output <behavior-hypothesis-ledger.json>
```

缺 predecessor、多个 leaf、重复 revision、fork、断链、循环、source tamper、缺失或
多余 observation artifact 均 fail-closed。输出 create-only，不覆盖已有路径。

## 验证与 source replay

```powershell
python -m src.investment_review behavior-hypothesis-ledger-validate `
  <ledger.json>

python -m src.investment_review behavior-hypothesis-ledger-validate `
  <ledger.json> --source-replay `
  --revision <chain-a-rev1.json> `
  --revision <chain-a-rev2.json> `
  --revision <chain-b-rev1.json> `
  --observation-artifact <p2g2-observations.json>
```

source replay 从显式 sources 重建整份 ledger 并比较 canonical bytes/content ID。

## AND 查询

```powershell
python -m src.investment_review behavior-hypothesis-ledger-query `
  <ledger.json> --view active `
  --status accepted `
  --episode-id <episode-id> `
  --evaluation-id <evaluation-id> `
  --actor <actor> `
  --reviewed-from "2026-07-01T00:00:00Z" `
  --reviewed-to "2026-08-01T00:00:00Z"
```

支持 `view`、status、hypothesis ID、episode ID、market context、evaluation ID、
source observation content ID、reviewed time window 和 actor。所有传入过滤器采用 AND
语义；查询结果是深拷贝，不改变 ledger。

## 安全渲染

```powershell
python -m src.investment_review behavior-hypothesis-ledger-render `
  --artifact <ledger.json> `
  --output <ledger.md>
```

Markdown 明示 active/audit 区别和非交易建议边界；自由文本、HTML、表格分隔符、标题
字符和控制字符会转义或替换。JSON ledger 始终是规范事实源。

阶段三完整功能边界、CLI/schema inventory、真实本地门禁结果和 remaining limitations
见 `reports/investment_review/p2g_stage3/P2G_STAGE3_CLOSE_READOUT.md`。推送后的 CI URL、
最终远端 SHA 和交付 ZIP hash 属于发布时回执，不反写 ledger 事实源。
