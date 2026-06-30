下面是我建议你进入 **P1：最小研究闭环** 的详细拆解。先说明边界：这是投研工作流与系统建设计划，不构成投资建议。

P1 的核心不是“研究很多细分”，而是用 **1 个细分方向** 跑通完整闭环：证据收集 → 细分定义 → 细分报告 → A 股公司池 → 1–2 家个股深度 → 细分-公司暴露映射 → 评分卡 → 观察清单 → 质量审查。你之前的路线图里也把 P1 定义为“用一个细分方向，跑通从输入细分到输出细分报告 + 公司池 + 个股深度的完整闭环”，重点 skills 是 `evidence-ingest`、`segment-research`、`company-universe`、`segment-company-mapping`、`stock-deep-dive`、`quality-review`。

---

# 一、P1 的总目标

## P1 一句话目标

> **选一个细分方向，建立一套可复用、可追溯、可审查的研究闭环，而不是追求全自动化或大规模覆盖。**

P1 完成后，你应该拿到这些成果：

```text
一个细分方向：
- 细分定义清楚
- 边界清楚
- 产业链清楚
- 核心指标清楚
- 证据链清楚
- A 股公司池清楚
- 1–2 家个股深度清楚
- 细分-公司暴露关系清楚
- 评分卡和观察清单清楚

```

P1 的底层原则仍然是：证据库是核心，报告只是证据库在某个时点的可再生视图；细分和公司是多对多关系，不能用文件夹层级强行表达。

---

# 二、P1 的范围控制

P1 最容易失败的原因是范围失控，所以先把边界钉死。

## P1 要做

```text
1. 只选 1 个试点细分。
2. 收集一批高质量证据。
3. 建立 evidence_manifest。
4. 生成初版 claims。
5. 生成细分研究报告。
6. 生成 A 股公司池。
7. 建立 segment_company_exposure 初版。
8. 选择 1–2 家公司做个股深度。
9. 生成细分评分卡、个股评分卡。
10. 输出观察清单和下一步研究队列。
11. 做一次 quality-review。

```

## P1 不做

```text
1. 不同时研究 20 个细分。
2. 不追求全自动抓取所有资料。
3. 不做全市场扫描。
4. 不做正式的多细分横向比较。
5. 不做复杂估值模型自动化。
6. 不做实时行情监控。
7. 不把评分当成买卖信号。

```

你原来的规划里也明确提醒：P1 不要同时研究 20 个细分，不要追求全自动资料抓取，不要让报告没有 `evidence_id`，不要把管理层表述、券商预测和事实混在一起，也不要让个股只属于一个细分。

---

# 三、P1 推荐试点对象

选试点细分时，不要选太宽的主题，比如“AI”“机器人”“半导体”，而要选能被边界化的细分。

推荐标准：

```text
1. 你本来就关注，后续会继续跟踪。
2. 有足够公开资料。
3. 有若干 A 股公司能映射。
4. 不至于宽到无法定义边界。
5. 能找到产品、订单、客户、募投、收入或技术储备等证据。

```

可选试点：

```text
AI服务器液冷
CPO
机器人丝杠
先进封装
固态电池设备
半导体量测设备
人形机器人传感器
数据中心电源
储能温控

```

我的建议是：**优先选“AI服务器液冷”或“机器人丝杠”**。这类细分既有产业链逻辑，又容易暴露“收入暴露、技术储备、市场叙事”之间的差异，适合验证你的 P1 系统。

---

# 四、P1 总流程

建议你按下面这条链路执行：

```text
P1-00：P0 健康检查
↓
P1-01：选择试点细分
↓
P1-02：建立细分定义卡
↓
P1-03：收集并登记证据
↓
P1-04：提取 claims 和关键指标
↓
P1-05：生成细分研究报告
↓
P1-06：生成 A 股公司池
↓
P1-07：建立 segment_company_exposure
↓
P1-08：选择 1–2 家个股
↓
P1-09：生成个股深度报告
↓
P1-10：生成评分卡和观察清单
↓
P1-11：quality-review
↓
P1-12：修正并固化模板
↓
P1-13：P1 复盘与进入 P2 判断

```

---

# 五、P1 详细任务拆解

## P1-00：P0 健康检查

### 目标

确认 P0 产物真的能支持 P1，不然后面会不断返工。

### 检查项

```text
1. AGENTS.md 是否存在。
2. .agents/skills/ 是否存在。
3. P1 需要的 6 个 skills 是否至少有 SKILL.md 空壳。
4. data/raw/、data/processed/、data/manifests/ 是否存在。
5. reports/segments/、reports/stocks/ 是否存在。
6. templates/segment_report.md 是否存在。
7. templates/stock_report.md 是否存在。
8. config/segment_taxonomy.yaml 是否存在。
9. config/source_registry.yaml 是否存在。
10. config/scoring_frameworks.yaml 是否存在。

```

### 交付物

```text
reports/p1/00_p0_readiness_check.md

```

### 完成标准

```text
P1 所需目录、模板、skills、配置都能找到；
没有关键文件路径不明确的问题。

```

---

## P1-01：选择试点细分

### 目标

确定 P1 只研究一个细分，避免范围膨胀。

### 任务

```text
1. 从候选细分中选一个。
2. 写清选择理由。
3. 写清暂不研究哪些相邻细分。
4. 写清研究时间范围。
5. 写清本轮只做到什么深度。

```

### 推荐输出

```yaml
p1_pilot_segment:
  segment_name_cn: AI服务器液冷
  segment_id: ai_server_liquid_cooling
  reason:
    - 公开资料较多
    - A股公司可映射
    - 容易区分收入暴露、技术储备和市场叙事
  date_range: 最近3年 + 最新公告/财报
  depth: standard_to_deep
  out_of_scope:
    - 普通工业液冷
    - 传统空调制冷
    - 非数据中心热管理

```

### 交付物

```text
reports/p1/01_pilot_segment_selection.md
config/segment_taxonomy.yaml 更新

```

---

## P1-02：建立细分定义卡

### 目标

先定义细分，不要直接开始写报告。

### 任务

```text
1. 生成 segment_id。
2. 写中文名、英文名、别名。
3. 写 scope_in。
4. 写 scope_out。
5. 写容易混淆的相邻细分。
6. 写产业链位置。
7. 写核心需求变量。
8. 写初版关键指标。

```

### 输出模板

```yaml
segment_id: ai_server_liquid_cooling
name_cn: AI服务器液冷
name_en: AI server liquid cooling
aliases:
  - 数据中心液冷
  - 服务器液冷
  - 冷板液冷
  - 浸没式液冷
scope_in:
  - AI服务器液冷相关设备、部件、系统集成
  - 数据中心液冷解决方案
scope_out:
  - 普通商用空调
  - 非服务器场景的工业冷却
  - 与AI服务器无关的传统制冷业务
related_segments:
  - 数据中心电源
  - 服务器结构件
  - 储能温控
industry_chain_role:
  - 设备
  - 零部件
  - 系统集成
key_questions:
  - 液冷渗透率是否提升？
  - A股公司收入暴露是否真实？
  - 毛利率和订单是否能兑现？

```

### 交付物

```text
config/segment_taxonomy.yaml 更新
reports/segments/<segment_id>/segment_definition.yaml
reports/segments/<segment_id>/segment_boundary.md

```

### 完成标准

```text
任何人看到定义卡，都能知道这个细分包含什么、不包含什么、和哪些概念容易混淆。

```

---

## P1-03：证据收集与登记

### 目标

建立 P1 的证据包。这里不是追求“全网最全”，而是建立可追溯、可复查、可复用的证据基础。

你之前给 `evidence-ingest` 设定的动作包括：检查 `source_registry.yaml`、获取或读取文件、计算 hash 去重、提取文本/页码/表格、写入 evidence 表、生成待审核 claims、更新 `evidence_manifest`。

### 证据优先级

```text
A类：官方披露
- 年报
- 半年报
- 季报
- 临时公告
- 募投说明
- 交易所问询回复
- 投资者关系活动记录表

B类：官方/准官方行业数据
- 工信部、发改委、统计局等
- 行业协会数据
- 交易所公开信息

C类：第三方研究
- 券商研报
- 咨询机构报告
- 行业媒体深度报道

D类：低置信度线索
- 新闻快讯
- 互动平台问答
- 会议纪要
- 市场传闻

```

### 建议最小证据量

```text
细分层证据：8–15 条
公司层证据：每家公司 2–5 条
总证据量：20–40 条即可

```

### evidence_manifest 字段

```csv
evidence_id,source_type,source_name,title,publisher,publish_date,raw_file_path,processed_text_path,file_hash,reliability_rank,related_segment,related_company,status,notes

```

### evidence_id 命名

```text
ev_<YYYYMMDD>_<source>_<entity>_<short_slug>_<hash6>

```

示例：

```text
ev_20250428_annual_report_300xxx_liquid_cooling_business_a1b2c3
ev_20260315_ir_002xxx_data_center_power_d4e5f6

```

### 交付物

```text
data/raw/<source_type>/...
data/processed/text/...
data/processed/tables/...
data/manifests/evidence_manifest.csv
reports/segments/<segment_id>/evidence_inventory.md

```

### 完成标准

```text
1. 每条证据有 evidence_id。
2. 每条证据有来源、日期、路径、可信度等级。
3. 原始文件不被覆盖。
4. 后续报告可以引用 evidence_id。

```

---

## P1-04：claims 提取与事实分类

### 目标

不要直接从证据跳到结论。先把证据拆成可复用的事实、管理层表述、估计、推断。

### claim_type 建议

```text
fact：事实
management_comment：管理层表述
analyst_view：券商/第三方观点
estimate：预测或估算
inference：你的推断
risk：风险或反证

```

### claims 表字段

```csv
claim_id,evidence_id,entity_type,entity_id,claim_text,claim_type,quote_or_excerpt,page_no,confidence,valid_until,notes

```

### 示例

```csv
claim_id,evidence_id,entity_type,entity_id,claim_text,claim_type,confidence
clm_ev_20250428_annual_report_300xxx_001,ev_20250428_annual_report_300xxx_liquid_cooling_business_a1b2c3,company,300xxx,公司披露数据中心液冷相关产品收入增长, fact, medium
clm_ev_20260315_ir_002xxx_001,ev_20260315_ir_002xxx_data_center_power_d4e5f6,company,002xxx,管理层表示液冷产品处于客户验证阶段, management_comment, low

```

### 交付物

```text
data/manifests/claims_draft.csv
reports/segments/<segment_id>/claims_review.md

```

### 完成标准

```text
1. 关键事实不是散落在报告里，而是沉淀成 claims。
2. 管理层表述和事实分开。
3. 预测和事实分开。
4. 推断和证据分开。

```

---

## P1-05：生成细分研究报告

### 目标

用固定模板生成第一版细分报告。

`segment-research` 的标准流程应包括：标准化细分名称和边界、明确 `scope_in / scope_out`、识别产业链位置、识别需求驱动、识别供给格局、建立关键指标体系、找出 A 股公司池、建立 `segment_company_exposure`、汇总证据和分歧、输出报告和证据地图。

### 细分报告结构

```md
# 细分方向研究：{{segment_name}}

## 0. Metadata
- segment_id:
- report_date:
- evidence_snapshot:
- confidence:
- last_refresh:

## 1. 一句话结论
- 事实：
- 推断：
- 主要不确定性：

## 2. 细分定义与边界
### 2.1 包含什么
### 2.2 不包含什么
### 2.3 相邻细分

## 3. 产业链位置
- 上游：
- 中游：
- 下游：
- 客户：
- 替代方案：

## 4. 需求驱动
- 核心需求变量：
- 量：
- 价：
- 渗透率：
- 周期性：

## 5. 供给与竞争格局
- 主要玩家：
- 壁垒：
- 产能：
- 成本曲线：
- 价格趋势：

## 6. 利润池分析
- 谁赚收入：
- 谁赚利润：
- 谁承担资本开支：
- 谁有议价权：

## 7. A股公司池
| 股票代码 | 公司 | 暴露类型 | 暴露分 | 证据 | 置信度 | 备注 |

## 8. 关键指标体系
| 指标 | 粒度 | 频率 | 来源 | 解释 |

## 9. 催化剂

## 10. 风险与反证

## 11. 评分卡

## 12. 后续跟踪清单

## 13. 证据地图

```

### 交付物

```text
reports/segments/<segment_id>/<YYYY-MM-DD>_segment_report.md
reports/segments/<segment_id>/evidence_map.md
reports/segments/<segment_id>/scorecard.yaml
reports/segments/<segment_id>/followup_questions.md

```

### 完成标准

```text
1. 每个关键结论都有 evidence_id 或 claim_id。
2. 事实、推断、假设、观点分开。
3. 不缺少反证和风险。
4. 缺数据的地方写 TODO，不编数字。

```

---

## P1-06：生成 A 股公司池

### 目标

找出和该细分相关的 A 股公司，但要区分“真实业务暴露”和“概念映射”。

公司池不应该只靠关键词搜索，而应分层：第一层是明确收入/产品暴露，第二层是产能/订单/客户暴露，第三层是技术储备/募投项目暴露，第四层才是市场叙事暴露。

### 暴露类型

```text
revenue：收入暴露
product：产品暴露
capacity：产能暴露
order：订单暴露
customer：客户暴露
technology：技术储备
fundraising_project：募投项目
narrative：市场叙事

```

### 暴露分

```text
5：有明确收入/利润占比，且细分贡献较大
4：有明确产品或订单，收入占比可大致判断
3：有产品/客户/项目证据，但收入占比不清
2：有技术储备、验证、小批量或募投方向
1：只有概念或间接关系
0：证据不足，暂不纳入

```

### company_universe.csv 字段

```csv
segment_id,stock_code,stock_name,company_id,exposure_type,exposure_score,revenue_pct,profit_pct,confidence,evidence_ids,notes,next_check

```

### 交付物

```text
reports/segments/<segment_id>/company_universe.csv
reports/segments/<segment_id>/company_universe_notes.md

```

### 完成标准

```text
1. 公司池不是简单股票列表。
2. 每家公司都有暴露类型。
3. 每家公司都有暴露分。
4. 每家公司都有 evidence_id。
5. 能区分“真收入暴露”和“概念暴露”。

```

---

## P1-07：建立 segment_company_exposure 初版

### 目标

把公司池变成系统可复用的多对多映射资产。

这是 P1 最重要的结构化产物之一，因为你的系统不能让一家公司只属于一个细分。原始设计里已经强调，`segment_company_exposure` 是解决“一个个股对应多个细分方向”的关键表。

### 推荐字段

```csv
segment_id,company_id,stock_code,stock_name,exposure_type,exposure_score,revenue_pct,profit_pct,evidence_id,confidence,valid_from,valid_to,notes

```

### 示例

```csv
ai_server_liquid_cooling,cn_300xxx,300xxx,公司A,revenue,4,25%,,ev_20250428_annual_report_300xxx_liquid_cooling_business_a1b2c3,medium,2025-01-01,,液冷产品有收入披露，但需进一步拆分毛利
ai_server_liquid_cooling,cn_002xxx,002xxx,公司B,technology,2,,,ev_20260315_ir_002xxx_data_center_power_d4e5f6,low,2026-03-15,,仍处客户验证阶段，不应等同业绩贡献

```

### 交付物

```text
data/normalized/segment_company_exposure.csv
reports/segments/<segment_id>/segment_company_exposure_review.md

```

### 完成标准

```text
1. 同一家公司可以属于多个细分。
2. 每条映射有证据。
3. 每条映射有置信度。
4. 每条映射能说明为什么纳入。

```

---

## P1-08：选择 1–2 家公司做个股深度

### 目标

不要把公司池里的所有公司都做深度。只选 1–2 家代表性公司验证个股研究流程。

### 选择方式

建议选两类：

```text
公司 A：暴露分最高、最像“核心标的”的公司。
公司 B：争议较大或概念映射较强的公司。

```

这样可以同时验证两种情况：

```text
1. 真暴露公司怎么研究；
2. 概念暴露公司怎么排除或降权。

```

### 输出

```md
# 个股深度样本选择

## 选择公司 A 的理由
- 暴露类型：
- 暴露分：
- 关键证据：
- 主要待验证问题：

## 选择公司 B 的理由
- 暴露类型：
- 暴露分：
- 关键证据：
- 主要待验证问题：

```

### 交付物

```text
reports/segments/<segment_id>/stock_deep_dive_selection.md

```

---

## P1-09：生成个股深度报告

### 目标

从细分进入个股，验证个股报告模板是否能承接证据库和细分映射。

`stock-deep-dive` 应覆盖公司业务拆解、财务质量、业务与多个细分方向的映射、客户/供应商/产能/订单/募投、估值场景、催化剂、风险、反证清单和横向比较。

### 个股报告结构

```md
# 个股深度：{{stock_code}} {{company_name}}

## 0. Metadata
- company_id:
- stock_code:
- report_date:
- evidence_snapshot:
- linked_segments:
- confidence:

## 1. 一句话结论
- 事实：
- 推断：
- 关键假设：
- 最大风险：

## 2. 公司业务拆解
| 业务 | 收入 | 毛利率 | 增速 | 关联细分 | 证据 |

## 3. 细分方向暴露
| 细分 | 暴露类型 | 收入占比 | 弹性 | 置信度 | 证据 |

## 4. 财务质量
- 收入：
- 毛利率：
- 净利率：
- 现金流：
- 应收/存货：
- 资本开支：
- ROE/ROIC：

## 5. 竞争优势

## 6. 客户与供应链

## 7. 管理层与治理

## 8. 估值
### 8.1 可比公司
### 8.2 情景假设
### 8.3 敏感性分析

## 9. 催化剂

## 10. 风险

## 11. 反证清单

## 12. 跟踪指标

## 13. 证据地图

```

### 交付物

```text
reports/stocks/<stock_code>_<company_name>/<YYYY-MM-DD>_stock_deep_dive.md
reports/stocks/<stock_code>_<company_name>/segment_exposure.yaml
reports/stocks/<stock_code>_<company_name>/evidence_map.md
reports/stocks/<stock_code>_<company_name>/open_questions.md

```

### 完成标准

```text
1. 个股报告能引用细分研究中的 evidence 和 claims。
2. 个股能映射到多个细分。
3. 业务、财务、估值、风险没有混在一起。
4. 有反证清单。
5. 没有无证据的关键结论。

```

---

## P1-10：生成评分卡和观察清单

### 目标

用评分卡把研究结果结构化，但不要把评分当成买卖建议。

你已有的评分体系强调“先粗后细，不要伪精确”，细分评分可覆盖市场空间、增速可见度、渗透阶段、供需结构、定价权、竞争质量、A 股纯度、业绩可见度、估值可接受度、催化剂、风险、证据质量等；个股评分可覆盖细分纯度、业绩弹性、财务质量、护城河、管理层执行、客户质量、估值空间、催化剂、下行风险、证据质量等。

### segment_scorecard.yaml

```yaml
segment_scorecard:
  segment_id: ai_server_liquid_cooling
  report_date: 2026-06-30
  scores:
    market_space: 4
    growth_visibility: 4
    penetration_stage: 4
    supply_demand_structure: 3
    pricing_power: 3
    competition_quality: 3
    A_share_purity: 4
    earnings_visibility: 3
    valuation_acceptability: 2
    catalyst_strength: 4
    policy_risk: 2
    cycle_risk: 3
    evidence_quality: 4
  final_priority: watch_high
  key_reasons:
    - reason:
      evidence_id:
  main_uncertainties:
    - uncertainty:
      evidence_id:

```

### stock_scorecard.yaml

```yaml
stock_scorecard:
  company_id: cn_300xxx
  stock_code: 300xxx
  linked_segments:
    - ai_server_liquid_cooling
  scores:
    segment_purity: 4
    earnings_elasticity: 4
    financial_quality: 3
    moat: 3
    management_execution: 3
    customer_quality: 4
    valuation_margin: 2
    catalyst_visibility: 4
    downside_risk: 3
    evidence_quality: 4
  final_priority: deep_watch
  key_reasons:
    - reason:
      evidence_id:
  kill_switches:
    - condition:
      evidence_needed:

```

### 观察清单

```yaml
watchlist_item:
  entity_type: company
  entity_id: cn_300xxx
  stock_code: 300xxx
  linked_segment: ai_server_liquid_cooling
  watch_reason:
    - 细分暴露分较高
    - 业绩弹性可能较大
  tracking_indicators:
    - 液冷相关收入占比
    - 订单兑现
    - 毛利率变化
    - 客户验证进展
    - 募投项目进展
  next_refresh_trigger:
    - 年报/半年报披露
    - 重大合同公告
    - 投资者关系活动记录
    - 行业价格或渗透率数据更新

```

### 交付物

```text
reports/segments/<segment_id>/scorecard.yaml
reports/stocks/<stock_code>_<company_name>/stock_scorecard.yaml
config/watchlist.yaml 初版
reports/p1/p1_watchlist.md

```

---

## P1-11：quality-review

### 目标

P1 不是写完报告就结束，而是要做一次质量门审查。

质量控制的重点是：结论有没有证据、证据是否可靠、数据口径是否一致、有没有把管理层表述当成事实、有没有把券商预测当成事实、有没有列出反证、有没有区分事实/推断/假设/观点。

### 检查清单

```text
证据检查：
- 所有关键结论是否有 evidence_id 或 claim_id？
- evidence_id 是否存在于 evidence_manifest？
- 是否引用了低置信度证据却没有标注？
- 是否存在过期证据？

事实/推断检查：
- 管理层表述是否被当成事实？
- 券商预测是否被当成事实？
- 行业空间测算是否标明假设？
- 个股收入暴露是否有直接证据？

指标口径检查：
- 收入、订单、产能、市占率是否混用？
- 同一指标在细分和个股报告中的口径是否一致？
- 财务指标是否有期间和来源？

反证检查：
- 是否列出竞争风险？
- 是否列出需求不及预期风险？
- 是否列出估值拥挤风险？
- 是否列出公司只是概念映射的可能性？

结构检查：
- 细分报告是否完整？
- 公司池是否有暴露分和置信度？
- 个股报告是否有 segment_exposure？
- scorecard 是否有证据支持？

```

### 交付物

```text
reports/p1/quality_review_<segment_id>.md
reports/p1/quality_issues.csv
reports/p1/fix_log.md

```

### 完成标准

```text
1. 所有 high severity 问题修复。
2. medium severity 问题要么修复，要么进入 TODO。
3. low severity 问题记录到后续优化。
4. 报告可以进入 P1 readout。

```

---

## P1-12：修正并固化模板

### 目标

P1 的价值不只是产出一份报告，而是发现模板和流程哪里不好用，然后固化成下一次可复用的流程。

### 任务

```text
1. 修正 segment_report.md 模板。
2. 修正 stock_report.md 模板。
3. 修正 company_universe.csv 字段。
4. 修正 segment_company_exposure 字段。
5. 修正 scorecard 维度。
6. 修正 evidence_card 模板。
7. 补充 skill 的 guardrails。

```

### 交付物

```text
templates/segment_report.md 更新
templates/stock_report.md 更新
templates/evidence_card.md 更新
config/scoring_frameworks.yaml 更新
.agents/skills/*/SKILL.md 更新
reports/p1/template_change_log.md

```

---

## P1-13：P1 readout 与复盘

### 目标

决定 P1 是否通过，以及是否进入 P2。

### P1 readout 结构

```md
# P1 Readout: {{segment_name}}

## 1. 本轮范围
- 试点细分：
- 时间范围：
- 证据数量：
- 公司池数量：
- 个股深度数量：

## 2. 核心产物
- segment_report:
- company_universe:
- scorecard:
- evidence_map:
- stock_deep_dive:
- segment_exposure:
- quality_review:

## 3. 主要结论
- 事实：
- 推断：
- 不确定性：

## 4. 系统验证结果
- 证据是否能沉淀：
- 结论是否能追溯：
- 公司是否能多对多映射：
- 报告是否能重建：
- 模板是否可复用：
- skill 边界是否清楚：

## 5. P1 问题清单
- 数据问题：
- 模板问题：
- skill 问题：
- 证据问题：
- 评分问题：

## 6. 是否进入 P2
- 判断：
- 理由：
- 前置修复项：

```

### 交付物

```text
reports/p1/p1_readout_<segment_id>.md
reports/p1/p1_lessons_learned.md
reports/p1/p2_entry_checklist.md

```

---

# 六、P1 任务看板

可以直接按这个看板推进。


| 编号    | 任务        | 主要 skill                           | 产物                                                | 完成标准                    |
| ----- | --------- | ---------------------------------- | ------------------------------------------------- | ----------------------- |
| P1-00 | P0 健康检查   | quality-review                     | p0_readiness_[check.md](http://check.md)          | P1 所需目录、模板、skills 完整    |
| P1-01 | 选择试点细分    | segment-research                   | pilot_segment_[selection.md](http://selection.md) | 只选 1 个细分，边界明确           |
| P1-02 | 建立细分定义卡   | segment-research                   | segment_definition.yaml                           | scope_in / scope_out 清楚 |
| P1-03 | 证据收集登记    | evidence-ingest                    | evidence_manifest.csv                             | 每条证据有 id、来源、路径、可信度      |
| P1-04 | claims 提取 | evidence-ingest                    | claims_draft.csv                                  | 事实、表述、估计、推断分开           |
| P1-05 | 细分报告      | segment-research                   | segment_[report.md](http://report.md)             | 关键结论有证据                 |
| P1-06 | 公司池       | company-universe                   | company_universe.csv                              | 公司有暴露类型、分数、证据           |
| P1-07 | 暴露映射      | segment-company-mapping            | segment_company_exposure.csv                      | 多对多映射可复用                |
| P1-08 | 选择个股      | stock-deep-dive                    | stock_[selection.md](http://selection.md)         | 选 1–2 家，理由清楚            |
| P1-09 | 个股深度      | stock-deep-dive                    | stock_deep_[dive.md](http://dive.md)              | 业务、财务、暴露、风险完整           |
| P1-10 | 评分和观察清单   | segment-research / stock-deep-dive | scorecard.yaml、watchlist.yaml                     | 评分有依据，不当买卖信号            |
| P1-11 | 质量审查      | quality-review                     | quality_[review.md](http://review.md)             | 高严重问题修复                 |
| P1-12 | 模板修正      | quality-review                     | template_change_[log.md](http://log.md)           | 模板和字段固化                 |
| P1-13 | P1 复盘     | memo-writer                        | p1_[readout.md](http://readout.md)                | 能判断是否进入 P2              |


---

# 七、P1 的 Codex 执行提示词

你可以在 Codex 里按阶段直接这样调用。

## 1. 启动 P1

```text
请基于当前 P0 工作区，启动 P1 最小研究闭环。

本轮只选择一个试点细分：{{细分名称}}。
目标是跑通：
证据收集 → 细分定义 → 细分报告 → A股公司池 → 1-2 个股深度 → 暴露映射 → 评分卡 → 观察清单 → quality-review。

要求：
1. 不做多细分比较；
2. 不追求全自动资料抓取；
3. 所有关键结论必须引用 evidence_id 或 claim_id；
4. 管理层表述、券商预测、事实、推断必须分开；
5. 缺数据的地方写 TODO，不要编造。

```

## 2. 细分研究

```text
$segment-research 调研“{{细分名称}}”，深度=standard_to_deep。

要求：
1. 先生成 segment_definition.yaml；
2. 明确 scope_in / scope_out；
3. 梳理产业链、需求驱动、供给格局、利润池；
4. 建立关键指标体系；
5. 输出 segment_report.md、scorecard.yaml、evidence_map.md；
6. 所有关键结论必须引用 evidence_id 或 claim_id。

```

## 3. 证据导入

```text
$evidence-ingest 为细分“{{细分名称}}”导入证据。

要求：
1. 优先官方公告、年报、半年报、投资者关系记录、交易所问询回复；
2. 每条证据生成 evidence_id；
3. 原始文件进入 data/raw/；
4. 提取文本进入 data/processed/text/；
5. 更新 data/manifests/evidence_manifest.csv；
6. 生成 claims_draft.csv；
7. 区分 fact、management_comment、analyst_view、estimate、inference。

```

## 4. 公司池

```text
$company-universe 基于细分“{{细分名称}}”生成 A 股公司池。

要求：
1. 不只按关键词纳入；
2. 按 revenue/product/capacity/order/customer/technology/fundraising_project/narrative 标注暴露类型；
3. 每家公司给 exposure_score 0-5；
4. 每家公司给 confidence high/medium/low；
5. 每家公司必须有 evidence_ids；
6. 输出 company_universe.csv。

```

## 5. 暴露映射

```text
$segment-company-mapping 基于 company_universe.csv 更新 segment_company_exposure。

要求：
1. 支持一家公司映射到多个细分；
2. 每条映射包含 segment_id、company_id、stock_code、exposure_type、exposure_score、evidence_id、confidence；
3. 对证据不足的公司标记 low confidence；
4. 输出 segment_company_exposure.csv 和 review.md。

```

## 6. 个股深度

```text
$stock-deep-dive 调研 {{股票代码}} {{公司名称}}，关联细分包括 {{细分名称}}。

要求：
1. 输出业务拆解；
2. 输出财务质量分析；
3. 输出细分暴露；
4. 输出客户、供应链、产能、订单、募投相关信息；
5. 输出估值场景，但所有假设必须标注来源或 TODO；
6. 输出风险和反证清单；
7. 输出 segment_exposure.yaml 和 evidence_map.md。

```

## 7. 质量审查

```text
$quality-review 审查 P1 产物。

范围：
1. reports/segments/{{segment_id}}/
2. reports/stocks/{{stock_code}}_{{company_name}}/
3. data/manifests/evidence_manifest.csv
4. data/manifests/claims_draft.csv
5. data/normalized/segment_company_exposure.csv

检查：
1. 关键结论是否有 evidence_id 或 claim_id；
2. evidence_id 是否存在；
3. 是否混淆事实、管理层表述、券商预测和推断；
4. 指标口径是否一致；
5. 是否缺少反证；
6. 是否存在无证据公司映射；
7. 是否存在伪精确评分。

```

---

# 八、P1 文件结构目标

P1 完成后，你的项目里至少应该新增这些文件：

```text
reports/
├── p1/
│   ├── 00_p0_readiness_check.md
│   ├── 01_pilot_segment_selection.md
│   ├── quality_review_<segment_id>.md
│   ├── quality_issues.csv
│   ├── fix_log.md
│   ├── template_change_log.md
│   ├── p1_readout_<segment_id>.md
│   ├── p1_lessons_learned.md
│   └── p2_entry_checklist.md
│
├── segments/
│   └── <segment_id>/
│       ├── segment_definition.yaml
│       ├── segment_boundary.md
│       ├── evidence_inventory.md
│       ├── claims_review.md
│       ├── <YYYY-MM-DD>_segment_report.md
│       ├── company_universe.csv
│       ├── scorecard.yaml
│       ├── evidence_map.md
│       ├── followup_questions.md
│       ├── segment_company_exposure_review.md
│       └── stock_deep_dive_selection.md
│
└── stocks/
    └── <stock_code>_<company_name>/
        ├── <YYYY-MM-DD>_stock_deep_dive.md
        ├── segment_exposure.yaml
        ├── stock_scorecard.yaml
        ├── evidence_map.md
        └── open_questions.md

data/
├── raw/
├── processed/
│   ├── text/
│   └── tables/
├── manifests/
│   ├── evidence_manifest.csv
│   └── claims_draft.csv
└── normalized/
    └── segment_company_exposure.csv

config/
├── segment_taxonomy.yaml
├── scoring_frameworks.yaml
└── watchlist.yaml

```

---

# 九、P1 验收标准

P1 不看报告写得多长，而看系统闭环是否成立。

你之前的 P1 验收标准包括：一个细分方向能被稳定研究，一个细分能生成 A 股公司池，一个公司可以映射到多个细分，报告中的关键结论能追溯证据，细分报告和个股报告格式稳定，并且能判断某家公司是真实业务暴露还是概念映射。

我建议把验收标准细化为 10 条：

```text
1. 有一个完整的 segment_definition.yaml。
2. 有一份带 evidence_id 的 segment_report.md。
3. 有一份 company_universe.csv。
4. company_universe 里每家公司都有暴露类型、暴露分、置信度和 evidence_ids。
5. 有一份 segment_company_exposure.csv。
6. 至少完成 1 家个股深度，最好 2 家。
7. 个股报告里能体现多细分暴露，而不是单一行业归类。
8. 有 segment_scorecard 和 stock_scorecard。
9. 有 quality_review，并修复高严重问题。
10. 有 p1_readout，能判断是否进入 P2。

```

---

# 十、P1 的暂停点

当你完成下面这些，就应该暂停，不要继续往 P2 冲：

```text
1. 一个细分方向已经跑通。
2. 这个细分有报告、公司池、评分卡、证据地图。
3. 至少 1 家公司有个股深度。
4. 个股能映射到多个细分。
5. 报告中关键结论能追溯证据。
6. quality-review 已经跑过。
7. 你已经记录了模板、字段、skill 边界上的问题。

```

然后先复盘：

```text
1. 模板是否好用？
2. evidence_id 引用是否麻烦？
3. claims 是否真的被复用？
4. 公司池是否能区分真暴露和概念暴露？
5. scorecard 是否太主观？
6. Codex 是否经常混淆 skill 边界？
7. 哪些流程值得脚本化？

```

---

# 十一、P1 到 P2 的进入条件

只有当下面条件满足时，才进入 P2：

```text
1. P1 的细分报告模板已经稳定。
2. P1 的个股报告模板已经稳定。
3. evidence_manifest 可以复用。
4. segment_company_exposure 可以复用。
5. quality-review 能发现实际问题。
6. company_universe 的字段足够支持横向比较。
7. scorecard 的维度基本稳定。
8. watchlist 能解释纳入理由和待验证事项。

```

否则不要急着做多个细分比较。P2 才是“多个细分和多个个股可以横向比较”的阶段，核心产物是 comparison matrix、watchlist 和 research queue。

---

# 十二、我建议你的 P1 执行顺序

最实用的推进顺序是：

```text
第 1 步：做 P0 readiness check。
第 2 步：选定一个试点细分。
第 3 步：先写 segment_definition.yaml，不写报告。
第 4 步：导入 20–40 条证据，形成 evidence_manifest。
第 5 步：从证据中提取 claims_draft。
第 6 步：生成细分报告初稿。
第 7 步：生成 company_universe.csv。
第 8 步：生成 segment_company_exposure.csv。
第 9 步：选 1–2 家公司做个股深度。
第 10 步：生成 scorecard 和 watchlist。
第 11 步：跑 quality-review。
第 12 步：修复高严重问题。
第 13 步：写 P1 readout。
第 14 步：判断是否进入 P2。

```

P1 的成败标准不是“这份研报是否漂亮”，而是：

> **下次换一个细分，能不能沿用同一套证据、模板、公司池、映射、评分和审查流程。**

---

# 十三、补充约束：以优秀案例校准生成质量

在 P1 计划的范畴内调试工作流和系统，不进行过多超出 P1 计划的建构。以 `docs/playbooks/stock_report_case_study_shengyi_tech.md` 作为个股研究报告质量参照，尽量让 P1 生成物接近该案例的结构完整度、业务拆分清晰度、财务分析密度、行业逻辑连贯性、催化剂梳理和风险/反证覆盖。

同时必须保留本项目的证据边界：所有关键结论仍需引用 `evidence_id`、`claim_id` 或 `metric_id`，事实、估计、推断、观点和管理层表述必须分开，缺失数据必须显式标记，不能为了接近案例的叙事质量而补造数字、来源或直接交易建议。
