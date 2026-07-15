# P2E-3 测试矩阵

以下用例是最低门阵。最终测试名和 fixture 应遵循仓库现有风格。

| ID | 层级 | 场景 | 关键断言 |
|---|---|---|---|
| T01 | Contract | 最小合法 artifact | schema validator 通过，必填字段完整 |
| T02 | Contract | 非法 Decimal/float | 浮点数和非法 Decimal 字符串被拒绝 |
| T03 | Determinism | 相同输入重复构建 | 字节内容与 `content_id` 完全相同 |
| T04 | Determinism | 输入 episode/event 顺序打乱 | canonical 输出顺序和 hash 不变 |
| T05 | Determinism | wall-clock 变化 | canonical payload/hash 不受生成时间影响 |
| T06 | Temporal | 未来成交修订 | `knowledge_cutoff` 后记录不被消费 |
| T07 | Temporal | 未来价格 | event 后或 cutoff 后价格不被消费 |
| T08 | Temporal | 未来行业分类 | 不用当前分类回填历史上下文 |
| T09 | Boundary | 单一成交 pre/post | pre 排除当前 event，post 包含当前 event |
| T10 | Ordering | 同秒多 fill 有序列号 | 使用业务序列，结果稳定 |
| T11 | Ordering | 同秒多 fill 无足够顺序信息 | 状态降级为 `ambiguous`，不猜顺序 |
| T12 | Ordering | 同秒现金快照不同插入顺序 | 多轮重排后选择结果与 hash 相同 |
| T13 | Revision | 同 effective time 多 knowledge/revision | 按双时间和显式 revision 选择 |
| T14 | Missing | 无可用组合快照 | context 保留，snapshot=`missing`，指标 missing |
| T15 | Missing | 未定价证券 | 覆盖率/警告正确，未知值不写 0 |
| T16 | Missing | 陈旧价格 | stale warning 与源价格时间可追溯 |
| T17 | Missing | 分类不完整 | 行业指标 missing/partial，不静默排除 |
| T18 | Linking | Decision unlinked/ambiguous/invalid | 原状态传播到 context，不制造确定链接 |
| T19 | Episode | 尚未平仓 | 不生成伪 close；open episode 可合法输出 |
| T20 | Delta | 两端方法版本兼容 | Decimal delta 正确、来源完整 |
| T21 | Delta | 方法/单位不兼容 | delta 为 null，返回结构化原因 |
| T22 | NAV | NAV 为零或负值 | 按现有口径明确 invalid/not_applicable，不除零 |
| T23 | Timezone | 不同时区等价时间 | UTC canonical 后锚点和 hash 一致 |
| T24 | Provenance | 每个可用指标 | method、version、source refs 非空且可解析 |
| T25 | Read-only | 构建前后源 DB | 文件/事务审计证明没有写入 |
| T26 | Revision | 补录历史数据后重建 | 新 `content_id`；旧 artifact 文件不变 |
| T27 | CLI | 正常构建 | stdout/exit code/输出路径符合现有规范 |
| T28 | CLI | validation/build 失败 | 非零退出，不留下半写文件 |
| T29 | Query | show/validate | 能按 episode/context/content ID 查询和验证 |
| T30 | Regression | clean checkout 全仓 | 无回归，结果计数和环境写入发布 manifest |

## 随机化/重复建议

T12 应至少对候选现金快照或事件的插入顺序做多种排列，或者用固定 seed 的 property-style 测试重复构建。目标不是“偶尔不失败”，而是证明选择逻辑与物理顺序无关。

## 测试分层

- 快速契约门：T01–T05；
- 核心构建门：T06–T26；
- CLI/发布门：T27–T30；
- CI 必须运行完整仓库测试，不只运行新增文件。
