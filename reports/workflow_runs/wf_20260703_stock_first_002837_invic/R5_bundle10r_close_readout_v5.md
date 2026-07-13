# Bundle 10R Reader v5 叙事修订关闭说明

## 关闭结论

| field | value |
|---|---|
| decision | `accepted_with_todos` |
| automated scope | `candidate_ready_for_human_review` |
| Reader | `R5_bundle10r_reader_v5.md` |
| Reader SHA256 | `cb261412f1c72dfd56e6dc9030c3d0f8bb06d4963a5525396059a6b1a21e6090` |
| Reader generation | `reader_gen_r5_bundle10r_v5_574937bd3943edc1` |
| human review | `pending` |
| sample quality / P2 | `false / false` |

本轮完成的是用户反馈后的版本化叙事修订，不是对 v4 历史产物的原地改写，也不包含人工审阅通过、sample-quality 恢复或 P2 许可。

## 已完成工作

- 将 v4 的 10 节重复审计脚手架改为 6 个问题驱动的读者章节。
- 底层 payload 继续保留 10 个非补偿分析单元，不降低证据、反证、观察条件或引用要求。
- 新增 v5 Writer、叙事 plan、v5 Reader contract 与 quality contract v2。
- 新增模板重复、流程术语、重复开头、段落相似度和标题碎片化门禁；v5 缺配置时 fail closed。
- 生成独立的 v5 payload、Reader、追溯附录、scorecard、人工 handoff 和六产物 generation lock。
- 将用户对 v4 的意见保存为独立 feedback artifact，并明确只覆盖叙事范围、未声明全篇审阅。

## 验证结果

| check | result |
|---|---|
| automated Reader gate | 100/82；truthfulness/core/candidate blockers = 0/0/0 |
| traceability | 22/22 display references 唯一解析 |
| narrative diagnostics | 4151 body Han chars；6 H2；31 paragraphs |
| anti-mechanical checks | repeated scaffold=0；process hits=0；similar paragraph pairs=0；thin sections=0 |
| deterministic generation | 6 artifacts rebuilt twice；hash changes=0 |
| v5 + lifecycle focused regression | 35 passed |
| full repository regression | 704 passed，2 skipped，28.78 秒 |
| v4 history compatibility | payload、report、appendix、scorecard、handoff 与 generation lock 从当前代码重建后均精确匹配原 SHA256 |

## 保留 TODO

| issue | owner | status | next action |
|---|---|---|---|
| `R5B10R-DCF-001` | company-valuation | accepted_todo | 补齐净债务、折现率和终值输入后重检方法资格 |
| `R5B10R-SOTP-001` | company-valuation | accepted_todo | 取得液冷独立经济性和消除关系后重检 |
| `R5B10R-V5-HUMAN-001` | quality-review / external reviewer | accepted_todo | 审阅 Reader v5 精确哈希与按需追溯附录 |
| `R5B10R-CI-001` | research-orchestrator | accepted_todo | 仅在用户明确授权发布后核验远端 CI |

`R5B10R-NARRATIVE-001` 已解决；Reader v4 的旧人工 TODO 以 `resolved_revision_required` 关闭，由新的 v5 人工 TODO 替代。

## 边界

没有新增未经审阅的事实或模型数字；没有把管理层近似口径、分析师观点或研究估计升级为发行人事实；没有做同业确定性排序；DCF 与 SOTP 仍停用；没有暂存、提交、推送或声明远端 CI。
