# Portfolio / Investment Review 选择性集成依赖清单

## 1. 基线与用途

本清单记录从 `origin/codex/portfolio-tracker` 向主研究系统做选择性集成时的
代码、文档和测试边界，也作为后续历史文档清理的依赖依据。

- 集成基线：`origin/main` `461a0c96b5920d4fc0265578fb7c24aa8cb073a0`
- 候选来源：`origin/codex/portfolio-tracker` `a0ad50a6ed6f7e0ccd0392613063367dcb30d319`
- 共同祖先：`08acbf9084dc32dade6d899ed3e8bbdbbc107efd`
- 原则：文件级迁移；不 merge 或整体 cherry-pick 产品分支。

正式账本 `C:\Projects\03_Investment_System\data\db\portfolio.sqlite3` 不属于
迁移输入。本次集成不读取业务行、不写入、不复制、不重建该文件，也不运行会修改它的
维护脚本。

## 2. 允许迁入

### 2.1 产品代码与前端

- `src/portfolio/**`：Portfolio 后端、前端源码、锁文件和三个 tracked
  `web_assets`；`web.py` 运行时直接读取后者。
- `src/investment_review/` 中属于当前 Review 产品路径的代码，但须减去第 5 节逐文件
  排除的四个历史 P10 模块；迁移和暂存必须按核对后的文件清单执行，不得整目录放行。
- `.agents/skills/portfolio-tracker/**`
- `.agents/skills/investment-review/SKILL.md`
- `scripts/start_portfolio_dashboard.ps1`
- `scripts/start_investment_review.ps1`
- `templates/broker_statement.template.csv`
- `templates/portfolio_opening_snapshot.template.csv`

### 2.2 安全配置与政策

- `config/investment_review.example.json`
- `config/investment_review.portfolio_snapshot.example.json`
- `config/portfolio_industry_taxonomy.json`
- `docs/policies/PERSONAL_HIGH_RISK_EQUITY_STRATEGY_CHARTER.md`
- `docs/playbooks/PORTFOLIO_TRACKER.md`
- `docs/playbooks/INVESTMENT_REVIEW_P2G_3.md`
- `docs/playbooks/INVESTMENT_REVIEW_P2G_4.md`
- `docs/playbooks/INVESTMENT_REVIEW_BEHAVIOR_HYPOTHESIS_LEDGER.md`

最后三份 Review playbook 仅保留其当前合同与测试作用，不是 Research workflow
事实源，也不授权 advice。

### 2.3 Review contracts

以下 20 个文件逐一允许；其中 18 个由 Review 运行时读取，两个以
`INVESTMENT_REVIEW_OPERATION_CHECKPOINT` 开头的 schema 仅由 reviewability 合同测试读取：

- `docs/contracts/INVESTMENT_REVIEW_OPERATION_CHECKPOINT.schema.json`
- `docs/contracts/INVESTMENT_REVIEW_OPERATION_CHECKPOINT_V2.schema.json`
- `docs/contracts/P2E_3_TRADE_EPISODE_PORTFOLIO_CONTEXT_DRAFT.schema.json`
- `docs/contracts/P2F_EPISODE_REVIEW_DRAFT.schema.json`
- `docs/contracts/P2F_HUMAN_REVIEW_REQUEST.schema.json`
- `docs/contracts/P2F_INTERPRETATION_OUTPUT_DRAFT.schema.json`
- `docs/contracts/P2F_REVIEW_INPUT_BUNDLE_DRAFT.schema.json`
- `docs/contracts/P2G_3_BEHAVIOR_HYPOTHESIS_ATTEMPT.schema.json`
- `docs/contracts/P2G_3_BEHAVIOR_HYPOTHESIS_RESPONSE.schema.json`
- `docs/contracts/P2G_3_BEHAVIOR_HYPOTHESIS_SET.schema.json`
- `docs/contracts/P2G_4_BEHAVIOR_HYPOTHESIS_REVIEW_REQUEST.schema.json`
- `docs/contracts/P2G_4_BEHAVIOR_HYPOTHESIS_REVISION.schema.json`
- `docs/contracts/P2G_BEHAVIOR_COHORT_DRAFT.schema.json`
- `docs/contracts/P2G_BEHAVIOR_HYPOTHESIS_LEDGER.schema.json`
- `docs/contracts/P2H_STAGE1_BEHAVIOR_HYPOTHESIS_CANDIDATE.schema.json`
- `docs/contracts/P2H_STAGE1_BEHAVIOR_HYPOTHESIS_PROJECTION.schema.json`
- `docs/contracts/P2H_STAGE1_BEHAVIOR_HYPOTHESIS_REVIEW_EVENT.schema.json`
- `docs/contracts/P2H_STAGE2_OBSERVATION_PROTOCOL.schema.json`
- `docs/contracts/P2H_STAGE2_OBSERVATION_PROTOCOL_PROJECTION.schema.json`
- `docs/contracts/P2H_STAGE2_OBSERVATION_PROTOCOL_REVIEW_EVENT.schema.json`

### 2.4 测试与 fixture

- 当前 Review 产品测试，但须减去第 5 节逐文件排除的四个历史 P10 测试；不得使用
  `tests/test_investment_review*.py` 通配暂存。
- `tests/test_portfolio*.py`
- `tests/test_personal_strategy_charter_policy.py`

只有以下四份合成 JSON fixture 允许迁入：

- `tests/fixtures/investment_review_p2c/scenario_manifest.json`
- `tests/fixtures/investment_review_p2h_stage1/candidate_draft.json`
- `tests/fixtures/investment_review_p2h_stage1/synthetic_observation_source.json`
- `tests/fixtures/investment_review_p2h_stage2/protocol_draft.json`

测试不得依赖 `reports/investment_review/**`。历史 P10 源码与测试在第 5 节明确排除；
原 P2G close-readout 文件依赖已改为验证当前政策、schema、playbook、CLI 和
`observation_only` 运行时行为。

## 3. main 原样保留

以下内容以 main 为权威，不从 Portfolio 分支覆盖：

- `docs/workflows/**`、所有 Research 代码、skills、schemas、tests 和报告。
- `src/utils/tushare_client.py`、`src/utils/tushare_diagnostics.py`、
  `src/ingest/adapters/tushare_adapter.py` 及 main 的 Tushare fetch 脚本和测试。
- `.env.example`：唯一 endpoint 为 `TUSHARE_HTTP_URL`；无 alias、内置 endpoint、
  `ts.set_token()` 或 token 持久化。
- `docs/playbooks/MANUAL_LIVE_DATA_SMOKE_PLAYBOOK.md`。
- `config/r5_readout_canonical_index.yaml.current_runs` 及其 current-pointer 语义。

Review 不是新的 Research `workflow_type`，不改变 G0-G10、P2 readiness、final-report
review 或 workflow-state 语义。

## 4. 只允许手工合并

以下文件以 main 为底，仅增加产品集成所需内容：

- `AGENTS.md`
- `README.md`
- `.codex/config.toml`
- `.github/workflows/ci.yml`
- `.gitignore`
- `.gitattributes`
- `pyproject.toml`
- `docs/index.md`
- `docs/meta/DOC_OWNERSHIP_MATRIX.md`
- `docs/policies/QUALITY_GUARDRAILS.md`
- `docs/project/PROJECT_CHARTER.md`
- `.agents/skills/investment-review/SKILL.md`
- `docs/playbooks/INVESTMENT_REVIEW_BEHAVIOR_HYPOTHESIS_LEDGER.md`
- `scripts/start_investment_review.ps1`
- `src/portfolio/frontend/vite.config.js`
- `src/portfolio/intraday.py`
- `src/portfolio/web.py`
- `tests/test_portfolio_tracker.py`
- `tests/test_investment_review_product_e2e.py`
- `tests/test_personal_strategy_charter_policy.py`
- `tests/test_investment_review_p2g_stage3_end_to_end.py`
- 本清单。

`pyproject.toml` 只增加 Review 的 `jsonschema>=4.18,<5` 强制依赖；Tushare、
pandas/openpyxl 和 Baostock 保持可选运行依赖。CI 在 main 的 Python/Research 检查上
增加 Node 22、前端测试、Vite build 和 tracked build 一致性检查。
`src/portfolio/web_assets/**` 只接受由本次前端源码和 Vite 配置确定性重建的结果，
不得手工编辑或从历史 report 复制。

## 5. 明确排除

- 全部 `docs/codex_tasks/**`、`docs/plans/**`、`docs/logs/**` 分支差异。
- 全部 `reports/investment_review/**`，包括 P8/P9/P10、periodic 样稿、close readout、
  acceptance、product-completion 与 phase reports。
- 全部历史 Research reports、workflow runs、R5/Bundle 与旧 builder WIP。
- 以下四个历史 P10 源文件，不进入迁移或暂存：
  - `src/investment_review/drawdown_validation.py`
  - `src/investment_review/strategy_account_reconstruction.py`
  - `src/investment_review/strategy_drawdown_pipeline.py`
  - `src/investment_review/strategy_market_data.py`
- 以下四个对应的历史 P10 测试，不进入迁移或暂存：
  - `tests/test_investment_review_drawdown_validation.py`
  - `tests/test_investment_review_strategy_account_reconstruction.py`
  - `tests/test_investment_review_strategy_drawdown_pipeline.py`
  - `tests/test_investment_review_strategy_market_data.py`
- `config/investment_review.portfolio.generated.json`
- `config/investment_review.portfolio.reviewed.json`
- `reports/investment_review/phase1/schema_manifest.json`
- `scripts/start_investment_review_acceptance.ps1`
- `scripts/stop_investment_review_acceptance.ps1`
- `scripts/backfill_portfolio_fees.py`
- `scripts/investment_review_p2d_review_pack.py`
- `scripts/portfolio_tracker.py`
- `.agents/skills/klinecharts/**`
- 三个 fixture README 和其他未列明 fixture。
- 数据库、`.env.local`、凭据、券商原始文件、PDF、截图、PNG、ZIP、缓存、
  `node_modules`、临时 build 和运行产物。

本地 generated/reviewed mapping 与 schema receipt 均被 Git 忽略。缺少有效的本地
reviewed mapping 时，Review 必须明确 unavailable；不得复制正式数据库、猜测 mapping
或回退到历史 tracked receipt。

## 6. 后续文档清理依据

后续清理可以安全地从“明确排除”项开始做引用审计，但本任务不删除文件或目录。
清理前至少复核：

1. 保留的 `src/investment_review/` 代码对 18 个 runtime contracts 的直接读取，以及
   reviewability 合同测试对两个 operation checkpoint schema 的读取；
2. P2G 合同测试对三份 playbook 的读取；
3. Portfolio 对行业 taxonomy、templates、frontend `web_assets` 的读取；
4. 所有测试对 fixture 的引用；
5. README、docs index 和 ownership matrix 不再链接历史 Review reports；
6. `reports/investment_review/**` 与本地 mapping 均不会进入暂存区。

UI 或阅读行为的验收必须绑定集成本地提交的 exact HEAD，使用合成临时数据库和产物，
不能用历史 reports 或正式 Portfolio 数据替代真人验收。
