# R5 下一阶段完成情况检查与任务包

## 1. 当前结论

最新工作区已经完成 R5-MVP 的目标定义雏形：仓库中已经出现 R5 spec、R5 research pack 模板、R5 report note 模板、R5 rubric、R5 Patch 0 task card 和 R5-MVP restructure plan。当前状态建议标记为：

```text
R5_MVP_SCOPE_DEFINED_WITH_BLOCKING_FORMAT_AND_VALIDATOR_GAPS
```

含义：方向已钉住，但还不是可执行 R5。下一阶段不要直接生成 R5 个股报告，而应先把 R5 变成“可解析、可校验、可 dry-run”的工程闭环。

## 2. 已完成项

1. R5-MVP 定位已建立：R5 不直接从 prompt 生成报告，而是先生成 `R5_stock_research_pack.yaml`，再转译成 `R5_stock_research_note.md`。
2. R5 研究包 12 个子包已经在文档里出现：company identity、evidence snapshot、financial history、business breakdown、segment exposure、industry context、peer comparison、forecast model、valuation、technical market、sentiment event、risk/counterevidence。
3. R5 章节结构已经出现：前言、财务概览、业务拆分、行业分析、盈利预测、估值分析、技术分析、情绪分析、事件驱动、研究结论。
4. no-advice、source gap 显式展示、缺 forecast/valuation/business 时降级等边界已经出现。
5. `stock-deep-dive`、`quality-review` 已经开始引用 R5 pack / R5 gate；`company-valuation` skill 已存在，可以作为估值分包的执行者。

## 3. 主要阻断项

### R5-BLOCK-001：Patch 0 文件格式与 YAML 可解析性风险

raw 视图显示 `templates/r5_stock_research_pack.yaml` 和 `benchmarks/r5_report_quality_rubric.yaml` 当前均为单行压缩内容。原 Patch 0 验收要求 `yaml.safe_load`，因此需要先让 Codex 在仓库中实跑并修复格式。该项必须优先于后续 schema / validator。

### R5-BLOCK-002：R5 validator 缺失

`stock-deep-dive` contract 中已经引用 `validate_r5_stock_research_pack.py`，但当前 scripts 目录未看到该脚本。没有 validator，R5 research pack 仍只是文档约定。

### R5-BLOCK-003：quality-review / segment-company-mapping 缺少可执行脚本

当前 `quality-review/scripts` 与 `segment-company-mapping/scripts` 基本为空，尚不能把 issue schema、exposure schema 变成可执行质量门。

### R5-BLOCK-004：forecast / valuation / technical / sentiment / catalyst 仍缺独立 schema 与示例

样例级报告最关键的差距是盈利预测、估值、技术面、情绪面、事件驱动。下一阶段必须先定义 schema 和 validator，不要让 writer 自由发挥。

### R5-BLOCK-005：R5 composer 尚未建立

目前还没有稳定的 “research pack -> report note” 转译层。R5 报告层必须只消费 pack，不得创造事实和数字。

### R5-BLOCK-006：R5 benchmark / dry-run 尚未落地

当前已有 rubric 初稿，但缺少 regression test 和 fixture dry-run。没有 dry-run 就不能宣称 R5-MVP 闭环完成。

## 4. 下一阶段目标

下一阶段目标不是“写出样例级英维克报告”，而是：

```text
R5_MVP_VALIDATABLE_CONTRACTS
```

达到该状态应满足：

1. R5 Patch 0 文件可读、可解析、可被测试。
2. R5 research pack 有 validator 和 example。
3. segment exposure 有 validator 和 example。
4. quality issue list 有 validator 和 example。
5. forecast / valuation 有 schema、example、validator。
6. technical / sentiment / catalyst 有 schema、example、validator。
7. R5 composer skeleton 可从 fixture pack 生成 note。
8. benchmark rubric 有 regression test。
9. 有一次 fixture stock-led dry-run，不写真实投资结论。
10. close readout 能明确列出 source gap、open questions、next tasks。

## 5. 推荐执行顺序

```text
Patch 0A  修复 Patch 0 格式与可解析性
Patch 1   R5 research pack validator + example
Patch 2   segment-company-mapping validator + examples
Patch 3   quality-review R5 issue validator + examples
Patch 4   forecast / valuation schema validators
Patch 5   technical / sentiment / catalyst pack schema validators
Patch 6   R5 report composer skeleton
Patch 7   R5 benchmark regression
Patch 8   R5 stock-led fixture dry-run
Patch 9   evidence-ingest R5 stock evidence plan
Patch 10  R5 close readout / task queue templates
Patch 11  sample report benchmark placeholder policy
Patch 12  company-valuation mini validator
```

## 6. 执行纪律

1. 一张任务卡只解决一个问题。
2. 每个 patch 必须有 readout。
3. 不修改历史 workflow run 产物，除非任务明确允许。
4. 不接真实 API，不抓 live 数据。
5. 不生成真实个股研究结论。
6. 不把 TODO / MISSING_DISCLOSURE 写成事实。
7. 不输出交易指令、仓位建议或可被解释为交易建议的内容。
8. high severity issue 不允许 accepted。
9. 缺 forecast / valuation / business / market snapshot 时不得标记 sample-quality。
