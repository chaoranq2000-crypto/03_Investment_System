# P2F 全阶段测试矩阵

本矩阵是最低门禁，不是最终测试文件名清单。真实路径和 fixture 必须在 P2E-3 完成后的精确 checkout 中映射。

## A. P2F-1 — Review Input Bundle

| ID | 场景 | 预期 |
|---|---|---|
| F1-01 | 相同输入重复构建 | `content_id` 完全一致 |
| F1-02 | source inventory 输入顺序重排 | 输出排序与 hash 不变 |
| F1-03 | Decimal 字段存在 | 不转换为二进制 float |
| F1-04 | future Decision | 被 `knowledge_cutoff` 排除 |
| F1-05 | future price/classification | 被排除并保留 warning |
| F1-06 | P2E-3 missing | portfolio section 明确 missing；完整发布门禁失败 |
| F1-07 | P2E-3 ambiguous | 候选 refs 与 ambiguous 状态传播 |
| F1-08 | stale/unpriced 指标 | 原样传播，不替换为 0 |
| F1-09 | open episode | 可构建，不伪造 close/outcome |
| F1-10 | invalid episode ref | validator 拒绝 |
| F1-11 | source content ID 改变 | bundle content ID 改变 |
| F1-12 | wall-clock metadata 改变 | canonical content ID 不变 |
| F1-13 | 输出写入失败 | 不留下半文件 |
| F1-14 | 构建前后 DB hash/transaction audit | 源库无写入 |

## B. P2F-2 — Facts-only Review

| ID | 场景 | 预期 |
|---|---|---|
| F2-01 | 完整输入 | 六个 fact sections 合法 |
| F2-02 | 时间线乱序输入 | 按稳定事件键排序 |
| F2-03 | 同秒 ambiguous 事件 | 不猜顺序，传播 ambiguous |
| F2-04 | 无 Decision | security/execution gap 显式化 |
| F2-05 | 无市场上下文 | market section missing，不伪造描述 |
| F2-06 | outcome 发生在 decision 后 | 标记 `known_after_episode` |
| F2-07 | outcome 文本试图作为 entry reason | policy/temporal validator 拒绝 |
| F2-08 | 事实没有 source ref | schema 或 semantic validator 拒绝 |
| F2-09 | 缺失值 | 不写为 0/false/none-as-fact |
| F2-10 | 计划与执行一致 | 只陈述可证明一致，不评价好坏 |
| F2-11 | 计划与执行偏离 | 陈述偏离并记录缺失原因 |
| F2-12 | 盈利结果 | 不自动判定决策正确 |
| F2-13 | 亏损结果 | 不自动判定决策错误 |
| F2-14 | facts-only render | 保留事实 ID 与来源 |
| F2-15 | 重复构建 | facts artifact 稳定 |
| F2-16 | 非法 temporal role | validator 拒绝 |

## C. P2F-3 — Bounded Interpretation

| ID | 场景 | 预期 |
|---|---|---|
| F3-01 | finding 无 fact ref | 拒绝 |
| F3-02 | finding 引用不存在 fact | 拒绝 |
| F3-03 | 心理诊断词且无证据 | policy gate 拒绝或降级 |
| F3-04 | 直接买卖建议 | policy gate 拒绝 |
| F3-05 | 机械总分 | policy gate 拒绝 |
| F3-06 | main tension 有替代解释 | 合法 |
| F3-07 | 可适用但替代解释为空 | release gate 阻止 |
| F3-08 | counterevidence 可用 | finding 必须携带引用 |
| F3-09 | 模型超时/不可用 | facts-only 输出成功 |
| F3-10 | 模型返回非法 JSON | 不覆盖事实 artifact；记录失败 |
| F3-11 | prompt/model 参数变化 | provenance 与输出 hash 更新 |
| F3-12 | 相同原始模型文本 | content hash 可复核 |
| F3-13 | outcome 污染事前解释 | temporal policy 拒绝 |
| F3-14 | 反事实使用事后最佳价 | policy gate 拒绝 |

## D. P2F-4 — Human Review and Revision

| ID | 场景 | 预期 |
|---|---|---|
| F4-01 | 接受 finding | 新 review event，原 artifact 不变 |
| F4-02 | 拒绝 finding | 状态可审计 |
| F4-03 | 纠正事实链接 | 生成新修订与 correction reason |
| F4-04 | supersedes 链 | 指向前一 content ID |
| F4-05 | revision chain 环 | validator 拒绝 |
| F4-06 | revision_no 回退/重复 | 拒绝 |
| F4-07 | 修改后 schema 非法 | 不写出最终文件 |
| F4-08 | render rev1/rev2 | 差异可见且来源保留 |
| F4-09 | Markdown 注入/控制字符 | 安全转义 |
| F4-10 | 人工审核 actor 缺失 | 拒绝 |
| F4-11 | correction 回写交易源库 | 明确禁止并测试只读 |
| F4-12 | 旧修订查询 | 可继续读取 |

## E. P2F-5 — End-to-End and Release

| ID | 场景 | 预期 |
|---|---|---|
| F5-01 | 完整 episode E2E | input → facts → interpretation → review → render 通过 |
| F5-02 | 缺失市场/Decision E2E | 降级成功且 warning 完整 |
| F5-03 | open episode E2E | 不伪造退出 |
| F5-04 | cutoff 回放 | 不消费未来数据 |
| F5-05 | clean checkout | 定向与全仓测试通过 |
| F5-06 | CI | 远端通过 |
| F5-07 | patch package | base/target、manifest、文件 hash 完整 |
| F5-08 | apply/rollback rehearsal | 可应用、可反向检查、不夹带脏改动 |

## F. 非功能与回归

- `python -m compileall -q .`
- P2F 定向测试；
- `python -m pytest -q`；
- 独立 clean checkout 重复全仓测试；
- 相同 fixture 多次循环，检测排序偶发性；
- Windows 与 POSIX 路径/换行兼容；
- UTF-8 中文与特殊字符；
- 大型 episode 的合理内存边界；
- 任何日志不得输出敏感交易数据全文；
- 默认命令不得调用模型或外网，除非显式启用。
