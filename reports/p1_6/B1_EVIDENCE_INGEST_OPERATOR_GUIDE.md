# B1 Evidence-Ingest Operator Guide

> 本文是给人类使用者看的 B1 操作说明。它不是 B2 研究启动文档，也不是投资判断、scorecard 或 watchlist 规则。

## 1. B1 是什么

B1 是 `evidence-ingest` 的证据导入层。

白话说，B1 负责把一份本地文件、一个 URL、一次 API 快照，变成仓库里可以检查、可以去重、可以追踪来源的证据记录。它会尽量回答这些问题：

- 这份材料是什么来源？
- 原始材料或快照有没有被归档？
- 是否和已有材料重复？
- 能不能解析出文本、表格或页面定位？
- 它应该写进 `evidence_manifest.csv` 的哪一行？
- 能不能生成草稿 claim、草稿 metric，或者只能记成 clue？
- 当前导入结果有没有通过校验？

B1 的输出是证据层材料，不是研究结论。

## 2. B1 解决什么问题

B1 解决的是“材料进仓库以后不会失控”的问题。

它把证据导入变成一套可重复的合同：

- 来源先分类，避免把新闻、传言、数据库快照、公告、年报混成同一种东西。
- 原始文件或 API 快照尽量归档，并记录归档策略。
- 用 hash 做去重，避免同一份材料变成多条 active evidence。
- 用 manifest 固定证据 ID、来源、日期、路径、hash、可信等级和候选生成状态。
- 用 draft candidate 承接“可能有用的信息”，但不直接升级为正式结论。
- 用 clue log 承接 D 级来源、失败探针、市场叙事等弱信号。
- 用 validator 和 debug cases 检查合同有没有被破坏。

## 3. B1 不解决什么问题

B1 不负责做研究判断。

它不做：

- B2 细分研究；
- 公司 universe 构建；
- 细分-公司暴露映射；
- 个股深度研究；
- scorecard；
- watchlist 纳入或移出；
- 投资备忘录；
- 买入、卖出、持有等直接交易指令；
- 把数据库指标直接解释成业务暴露；
- 把 D 级来源升级成材料性结论。

如果 B1 生成了 `claim_candidates` 或 `metric_candidates`，它们仍然只是草稿。后续必须经过质量检查或人工 review，才可能进入正式 claim / metric registry。

## 4. B1 操作流程

操作者可以把 B1 理解成下面这条链：

```text
input file / URL / API snapshot
        |
        v
classify source
        |
        v
archive raw
        |
        v
hash dedup
        |
        v
parse / snapshot
        |
        v
write evidence_manifest
        |
        v
generate claim_candidates / metric_candidates / clue_log
        |
        v
validate
        |
        v
readout
```

这里最重要的不是“生成了多少内容”，而是每一步都留下能追溯的记录。B1 宁可把问题标成 TODO、MISSING、LOW_CONFIDENCE 或 blocked，也不要把不确定材料包装成结论。

## 5. 文件和目录职责

| 路径 | 职责 | 日常怎么看 |
|---|---|---|
| `.agents/skills/evidence-ingest/SKILL.md` | `evidence-ingest` 的入口合同。说明什么时候用、什么时候不用、标准流程、输出边界、校验脚本和 no-advice guardrails。 | 需要确认 skill 边界时读它。它告诉你 B1 能做什么，不能做什么。 |
| `.agents/skills/evidence-ingest/references/` | B1 的详细规则库。包括来源类型、source registry 合同、ingest mode、manifest 字段、候选生成、质量门、失败处理、结构化数据边界等。 | 日常理解 B1 时优先读这里，而不是先读 Python 源码。 |
| `.agents/skills/evidence-ingest/scripts/` | 可执行工具目录。包含 hash 计算、manifest 校验、路径校验、候选校验、debug cases、ingest log 写入和 legacy manifest 迁移脚本。 | 需要跑校验、复现 debug case 或定位失败时再看。不要把脚本当成第一阅读入口。 |
| `.agents/skills/evidence-ingest/assets/` | 样例、模板和 debug fixtures。包括 example manifest、claim/metric/clue 样例、parse log 模板和五个 B1 debug cases。 | 用来理解“合格输入/输出长什么样”，也被测试和 readout 用来证明合同可运行。 |
| `data/manifests/evidence_manifest.csv` | 证据总清单。每行是一条 evidence 记录，记录来源、标题、日期、路径、hash、归档策略、可信等级、候选状态、review 状态等。 | 先看它确认证据是否被登记、是否 active、是否有 hash、是否有 raw/processed 路径。 |
| `data/manifests/claims_draft.csv` | claim 草稿候选。记录可能来自证据的事实、管理层表述、估计、分析师观点、风险或 clue 等。 | 这里只是草稿，不是正式 claim。重点看 `claim_type`、`evidence_id`、locator、review 状态和 notes。 |
| `data/manifests/metrics_draft.csv` | metric 草稿候选。记录结构化数值、期间、单位、口径、来源证据和估计/披露标记。 | Tushare / Baostock 这类结构化数据默认只能支持 metric，不证明业务暴露。 |
| `data/manifests/clue_log.csv` | 线索日志。承接 D 级来源、失败探针、市场叙事或只能后续验证的弱信号。 | clue 不能单独支持材料性结论，只能触发 TODO 或后续证据搜索。 |
| `reports/p1_6/B1_EVIDENCE_INGEST_DEBUG_READOUT.md` | B1 当前验收读数。记录 debug cases、命令、校验结果、已解决问题、剩余 TODO 和是否启动后续阶段。 | 日常想快速理解 B1 当前状态，先读 readout；再按需要回到 references。 |

## 6. 五个 debug cases 怎么理解

### 6.1 `manual_file_success`

这是“手动导入一个本地文件”的成功样例。

它证明 B1 能把一个明确的本地材料登记成 manifest 行，并让 manifest validator 通过。操作者可以把它当成最小成功路径：有文件、有元数据、有 hash、有来源分类、有合法状态。

### 6.2 `local_dir_duplicate`

这是“本地目录里出现重复文件”的样例。

它证明 B1 不应该因为同一份内容出现两次，就写出两条 active evidence。重复材料应通过 hash 被识别，结果应记录为 `SKIPPED_DUPLICATE` 或类似状态，并指向已有 evidence，而不是重复污染证据库。

### 6.3 `structured_api_pull_snapshot`

这是“结构化 API 快照”的样例，典型理解对象是 Tushare / Baostock 这类结构化数据源。

它证明 API 拉取结果应被保存为快照，并进入 metric 候选路径。它可以产生 `metric_candidates`，但不能证明公司业务暴露、订单、客户、细分收入占比或投资逻辑。结构化数据默认是 `metric_only`。

### 6.4 `d_source_clue_blocked`

这是“D 级来源只能当线索”的样例。

D 级来源包括新闻、社交媒体、热榜、市场叙事、概念标签等弱来源。B1 的规则是：这类来源不能支撑材料性 claim。如果有用，只能进 `clue_log.csv` 或 TODO，等待后续用 A/B/C 级证据核验。

### 6.5 `invalid_manifest_failure`

这是“故意放一个坏 manifest，看 validator 是否能拦住”的样例。

它证明 B1 的校验不是摆设。比如状态枚举错误、D 级来源试图支持材料性 claim、把 URL 写进本地路径字段、缺少应该存在的路径、日期异常等，都应该被挡住。这个 case 通过的含义不是坏数据可用，而是坏数据确实被识别为失败。

## 7. 日常阅读顺序

日常理解 B1，不需要先读 Python 脚本源码。

推荐顺序：

1. 先读 `reports/p1_6/B1_EVIDENCE_INGEST_DEBUG_READOUT.md`，了解当前 B1 是否通过、还剩哪些 TODO。
2. 再读 `.agents/skills/evidence-ingest/references/`，理解来源分类、manifest 字段、候选规则和质量门。
3. 需要确认 skill 使用边界时，读 `.agents/skills/evidence-ingest/SKILL.md`。
4. 只有在要复现校验、定位失败、扩展脚本或排查 debug case 时，再读 `.agents/skills/evidence-ingest/scripts/`。

## 8. 当前硬化状态

### 8.1 `raw_archive_hardening_needed`

状态：已完成。

2026-07-02 的 B1 evidence-chain hardening 已把原先的官方、行业、政策轻归档记录补齐为可复核 raw archive。现在 `evidence_manifest.csv` 中 `evidence_card_only` 行数为 0，相关记录已有 `raw_file_path` 和完整 `file_hash`。

注意：这不等于自动生成研究结论。官方披露和政策材料可以作为后续 material claim 的候选支撑，但仍需要页码、章节、表格定位和 review；行业报告仍按 source registry 保持 `material_claim_allowed=false`，只能做背景、估计、分析视角或线索，不能替代公司官方披露。

### 8.2 `api_params_hash_backfill_or_next_pull_needed`

状态：已完成。

2026-07-02 的 B1 evidence-chain hardening 已为现有 Tushare 快照补齐参数 JSON 和 `api_params_hash`。参数文件位于：

```text
data/raw/market_data/api_params/*__api_params.json
```

以后再次拉取 Tushare / Baostock 等 API 时，仍要继续保存完整 params、fields、date range、retrieved_at，并计算 `api_params_hash`。结构化数据仍默认是 `metric_only`，不能直接证明业务暴露。

## 9. 进入 B2 前我应该能回答的 10 个问题

1. B1 的输入可以是哪几类材料？本地文件、URL、API snapshot 分别会走什么路径？
2. 一条 evidence 进入 `evidence_manifest.csv` 时，哪些字段是最低必需的？
3. `source_type`、`source_name`、`source_group`、`reliability_rank` 分别解决什么问题？
4. A/B/C/D 级来源分别能支持什么，D 级来源为什么只能做 clue 或 TODO？
5. Tushare / Baostock 这类结构化数据为什么默认只能 `metric_only`？
6. `raw_archive_policy` 里的 `full_file_archived`、`snapshot_archived`、`metadata_only`、`evidence_card_only` 有什么差别？
7. hash 去重失败会造成什么问题？重复材料应该怎样记录？
8. `claims_draft.csv`、`metrics_draft.csv`、`clue_log.csv` 的边界分别是什么？
9. 哪些 validator 或 debug cases 能证明 B1 合同没有被破坏？
10. 如何确认 B1 硬化状态仍然有效：`evidence_card_only` 是否为 0，结构化快照是否都有 `api_params_hash`，以及 validator 是否通过？

## 10. 最后提醒

B1 是证据入口和合同层，不是研究结论层。进入 B2 前，应确认 B1 的 readout、manifest、draft candidates、clue log 和硬化状态都能被解释清楚；不能把 B1 产物直接当成 scorecard、watchlist 或投资判断。
