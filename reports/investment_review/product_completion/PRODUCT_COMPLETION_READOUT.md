# 投资复盘产品完成候选验收

## 结论

`investment_review_product_completion_v2` 已达到冻结合同定义的本地 verified candidate：工程闭环完成，正式来源在记录的稳定 cutoff 上已对账，全部 completion criteria 有证据；但历史人类决策和正式组合快照仍缺失，因此真实复盘保持 `facts_only / partial / unknown`，没有被包装成 ready。

- `engineering_complete=true`
- `data_ready_at_recorded_cutoff=true`
- `human_context_complete=false`
- `human_product_acceptance=false`
- `production_released=false`

没有 push、PR、merge、tag、release、部署、外部 provider 或 OS scheduler。

## v1 阻断与 v2 修订

v1 包为 `docs/codex_tasks/investment_review_product_completion_v1`，合同 SHA-256 为 `86d6ba6f4f4365fac03c5ed8797f381d1b888563d84239e3a933be2473e130c6`。它在 P1 前硬停止：reviewed mapping 登记的 generated mapping SHA-256 是 `a707064ba00cc8795e7e6164b5b7240b4c86a55f7a9aaa4433af3b26cd498b9e`，而正式只读 schema 重建结果是 `bbe59f0dd126933e89c8580a2281893078e3b76baa5c61cac98355da0986d4f3`，严格 validator 因 provenance 不匹配而拒绝继续。

用户随后明确确认 D-010 映射语义并授权 v2 amended package。v2 只增加一个受限动作：从正式源 schema 只读重建 machine mapping、登记新 provenance，再继续原有五阶段目标；没有扩大产品、数据写入或发布权限。v2 包合同 SHA-256 为 `96973061c04b2cdb1f86b2140efba475e35b623dd45b939d609a0914d1ea922f`，source baseline 为 `5a5f02a71ddbdfe8c3327c49ab45ee67e777b79b`。

## Mapping provenance

正式来源仍为 `C:\Projects\03_Investment_System\data\db\portfolio.sqlite3 / ledger_entries`。

| 项目 | 结果 |
|---|---|
| 旧登记 generated SHA-256 | `a707064ba00cc8795e7e6164b5b7240b4c86a55f7a9aaa4433af3b26cd498b9e` |
| 重建并登记 generated SHA-256 | `bbe59f0dd126933e89c8580a2281893078e3b76baa5c61cac98355da0986d4f3` |
| schema manifest SHA-256 | `a4e23bf8d6bfe8b0cd15d2241e65fca1fe0305b7ffb3495fd57abaee9c4b34f0` |
| reviewed content SHA-256 | `2eddc1c2aafe221fcd94c2c51d84c646174df5489b73bfcf1c171f55988c1c8a` |
| reviewed file SHA-256 | `8529ea00a4f9b2c3dd9518ad8039bf479e5c81c48964be74edc49c0539a3b15e` |
| reviewer / time | `workspace_user` / `2026-07-23T15:49:28+08:00` |
| strict validator | pass；table schema `26a979d503a276afa0e42957c90878eb479ab63bcd7d59374366525c959c79bf` |

D-010 业务语义没有变化：identity 为 `account_id + "::" + external_id`；`occurred_at` 由 `event_date + event_time` 构造；没有独立 `known_at` 时显式回退到 `occurred_at` 并标记 fallback；`created_at` 不是历史 known time；BUY/SELL 保持交易方向，DIVIDEND/CASH_FEE 映射为 OTHER；币种为 CNY。

## 数据与正式运行

正式 portfolio DB 从 preflight 到最终验证始终以 SQLite `mode=ro` 使用：

- 初始/最终 SHA-256 均为 `752e3b87966f23d2e6f3db89cd3a8d5df0ab893504ee4e7e83de793e4aa52f53`
- `PRAGMA quick_check=ok`
- `ledger_entries=983`
- 用户原 sidecar 初始/最终 SHA-256 均为 `4eb58f12e2888d3761107e2d23f06efd69096e3525b955a1e96d4bcc092dae38`

候选 sidecar 位于本执行 worktree，Git 忽略，最终 `quick_check=ok`，SHA-256 为 `3d996f7a0493e1dd63b3883609f0494fc47d0e9a4939debb0bca63b82d353564`。

稳定 cutoff `sync_cutoff_3d178827a8baa26f37fb050c` 的最大 effective/knowledge time 均为 `2026-07-17T05:55:28Z`：

| 项目 | 数量 |
|---|---:|
| source / sidecar / unsynced | `983 / 983 / 0` |
| 重复 apply inserted / skipped | `0 / 983` |
| fee actual / estimated / unknown | `192 / 693 / 30` |
| fee profiles / projections | `75 / 915` |
| candidate decisions / links | `0 / 0` |
| candidate portfolio snapshots / items | `0 / 0` |

single、weekly、monthly 都完成 dry/apply/repeat 和 source replay。它们分别选择 `1 / 22 / 25` 个 episode，产生 `23 / 485 / 629` 条 facts；跨范围共有 25 个唯一 episode/review。所有 scope 为准确的 `partial`，source-replay stage 为 `ready`。运行明确记录：`facts_only=true`、`historical_decisions_inferred=false`、`model_called=false`、`no_advice=true`、`portfolio_source_written=false`。

## 自动化闭环

P5 增加的是可关闭的进程内 catch-up，不是系统任务。成功的 portfolio transaction 只做非阻塞 enqueue；review 失败不会回滚 portfolio import。

- 首次正式候选 cycle：`partial`
- catch-up run：`reviewrun_49e211b834a87a77d769b4d1856c968e`
- 顺序：`single → weekly → monthly`
- 同一输入立即重放：`deduplicated`，候选 sidecar 哈希不变
- startup catch-up：收敛到 `partial`
- worker stop：有界完成，停止后 `worker_alive=false`
- disabled mode：不创建任务、不运行 scope
- health：路径已裁剪，显示 queue/latest/last completed/last failure 与三种 scope

自动化测试覆盖并发 dedupe、producer/consumer lease、崩溃恢复、持续输入漂移的有界重试、失败 scope 重试、跨协调器状态恢复、terminal/pending dedup 恢复、startup/periodic/stop 和 portfolio rollback 隔离，共 `17 passed`。

## API、UI 与浏览器

正式 episode `review:61ce0f537dfb7bce24f1fb4393455716 / te_92f0638df6c3ba18b798b3d7379c7278` 只查看，没有提交人类内容。页面显示 `source 983 / sidecar 983 / unsynced 0`、费用三态、`automation partial`、last completed，以及 facts-only、missing snapshot、unlinked decision 和不可纠正边界。

“查看—补充—纠正—保存”仅在独立 synthetic 浏览器 fixture 中写入，输入带有 `SYNTHETIC` 标识；revision 2、human-authored correction、替换 fact 和 synthetic note 刷新后均可见。它们没有进入正式来源、正式候选 sidecar或用户 sidecar。

六个 GET surface 均返回 200 且无路径泄露；非法 run ID 返回 `invalid_run_id`，hostile Host 返回 `host_not_allowed`。页面日志为空。浏览器插件向 `ab.chatgpt.com` 的 Statsig 遥测曾超时，但 localhost 页面请求和验收均成功；该外部遥测不是候选页面错误。

证据位于：

- `.codex_tmp/investment_review_product_completion_v2/browser_smoke/p5_steps.json`
- `.codex_tmp/investment_review_product_completion_v2/browser_smoke/p5_api_smoke.json`
- `.codex_tmp/investment_review_product_completion_v2/browser_smoke/p5_formal_automation.jpg`
- `.codex_tmp/investment_review_product_completion_v2/p5_automation/candidate_automation_smoke.json`

## 验证结果

所有 Python 命令均使用
`C:\Projects\03_Investment_System\.conda\investment-system\python.exe`。

| ID | 结果 |
|---|---|
| V-001 | package valid/ready，contract hash 匹配 |
| V-002 | source `quick_check=ok`，前后 SHA-256 相同 |
| V-003 | doctor 重建 hash 匹配；D-010 和严格 validator 通过 |
| V-101 | `30 passed` |
| V-201 | `84 passed` |
| V-202 | dry/apply/repeat/status：`983/983`，`unsynced=0`，重复 `inserted=0` |
| V-301 | `267 passed` |
| V-302 | 三范围 dry/apply/repeat 确定；source replay ready |
| V-401 | `49 passed` |
| V-402 | `16 passed`，Vite build `9 modules` |
| V-403 | 正式数据只读；synthetic note/correction 持久化；API/browser 边界通过 |
| V-501 | `1524 passed, 2 skipped in 445.05s`；通过数高于 1401，skip 未高于基线 2 |
| V-502 | `git diff --check` 与范围审查通过；checkpoint 后 clean proof 写入忽略的 `final_git_proof.json` |
| V-999 | C-MAP-001 至 C-REL-001 全部有定位证据；`production_released=false` |

实际命令与等价只读方法如下；V-202/V-302 的每次运行均把独立 JSON 回执写入表中所列忽略目录。

```powershell
# V-001
& $PY C:\Users\Q\.codex\skills\autonomous-stage-runner\scripts\task_package.py validate docs\codex_tasks\investment_review_product_completion_v2 --require-ready

# V-002
Get-FileHash C:\Projects\03_Investment_System\data\db\portfolio.sqlite3 -Algorithm SHA256
# 同时用 SQLite URI mode=ro、PRAGMA query_only=ON 执行 PRAGMA quick_check

# V-003
& $PY -m src.investment_review doctor --portfolio-db C:\Projects\03_Investment_System\data\db\portfolio.sqlite3 --out .codex_tmp\investment_review_product_completion_v2\p5_mapping_recheck_schema.json --mapping-out .codex_tmp\investment_review_product_completion_v2\p5_mapping_recheck.generated.json --table ledger_entries --include-counts
# 加载 reviewed mapping，调用 _require_reviewed_sqlite_mapping，并重算 reviewed_mapping_content_sha256
Get-FileHash config\investment_review.portfolio.generated.json,.codex_tmp\investment_review_product_completion_v2\p5_mapping_recheck.generated.json -Algorithm SHA256

# V-101
& $PY -m pytest -q -p no:cacheprovider tests/test_investment_review_fee_estimation.py tests/test_investment_review_product_store.py tests/test_investment_review_phase1.py

# V-201
& $PY -m pytest -q -p no:cacheprovider tests/test_investment_review_sync_service.py tests/test_investment_review_fee_estimation.py tests/test_portfolio_tracker.py

# V-301
& $PY -m pytest -q -p no:cacheprovider tests/test_investment_review_review_runner.py tests/test_investment_review_trade_episodes.py tests/test_investment_review_episode_portfolio_context.py tests/test_investment_review_review_input_bundle.py tests/test_investment_review_episode_review.py tests/test_investment_review_p2f_e2e.py

# V-401
& $PY -m pytest -q -p no:cacheprovider tests/test_investment_review_product_api.py tests/test_investment_review_product_e2e.py tests/test_portfolio_web.py

# P5 automation
& $PY -m pytest -q -p no:cacheprovider tests/test_investment_review_product_automation.py
$env:PYTHONPATH = (Get-Location).Path
& $PY .codex_tmp\investment_review_product_completion_v2\p5_automation\run_candidate_smoke.py

# V-402
Push-Location src\portfolio\frontend
npm test -- --run
npm run build
Pop-Location

# V-403
& $PY .codex_tmp\investment_review_product_completion_v2\browser_smoke\server_harness.py
# 浏览器：正式数据只读查看；隔离 fixture 写入 SYNTHETIC note/correction；刷新、证据抽屉、截图
& $PY .codex_tmp\investment_review_product_completion_v2\browser_smoke\p5_api_smoke.py

# V-501
& $PY -m pytest -q -p no:cacheprovider

# V-502
git diff --check
git status --short
git log --oneline 5a5f02a71ddbdfe8c3327c49ab45ee67e777b79b..HEAD
git diff --name-status 5a5f02a71ddbdfe8c3327c49ab45ee67e777b79b..HEAD
git diff --name-only 5a5f02a71ddbdfe8c3327c49ab45ee67e777b79b a597b94a4e01a9c1ac220f9e9220997288734deb
```

V-202 的四条实际 CLI 命令：

```powershell
& $PY -m src.investment_review --db data\db\investment_review.sqlite3 review-sync --portfolio-db C:\Projects\03_Investment_System\data\db\portfolio.sqlite3 --mapping config\investment_review.portfolio.reviewed.json --dry-run --out .codex_tmp\investment_review_product_completion_v2\p5_final_sync\01_dry_run.json
& $PY -m src.investment_review --db data\db\investment_review.sqlite3 review-sync --portfolio-db C:\Projects\03_Investment_System\data\db\portfolio.sqlite3 --mapping config\investment_review.portfolio.reviewed.json --apply --out .codex_tmp\investment_review_product_completion_v2\p5_final_sync\02_apply.json
& $PY -m src.investment_review --db data\db\investment_review.sqlite3 review-sync --portfolio-db C:\Projects\03_Investment_System\data\db\portfolio.sqlite3 --mapping config\investment_review.portfolio.reviewed.json --apply --out .codex_tmp\investment_review_product_completion_v2\p5_final_sync\03_repeat_apply.json
& $PY -m src.investment_review --db data\db\investment_review.sqlite3 review-sync-status --portfolio-db C:\Projects\03_Investment_System\data\db\portfolio.sqlite3 --mapping config\investment_review.portfolio.reviewed.json --out .codex_tmp\investment_review_product_completion_v2\p5_final_sync\04_status.json
```

V-302 用以下循环展开为 single/weekly/monthly 各自的 dry/apply/repeat 共九次调用：

```powershell
$common = @(
  '-m','src.investment_review','--db','data\db\investment_review.sqlite3',
  'review-run','--portfolio-db','C:\Projects\03_Investment_System\data\db\portfolio.sqlite3',
  '--mapping','config\investment_review.portfolio.reviewed.json',
  '--as-of','2026-07-17T05:55:28Z',
  '--knowledge-cutoff','2026-07-17T05:55:28Z',
  '--artifact-root','.codex_tmp\investment_review_product_completion_v2\p5_final_runs\artifacts',
  '--trigger','p5_final_v302'
)
foreach ($scope in @('single','weekly','monthly')) {
  foreach ($mode in @('dry','apply','repeat')) {
    $flag = if ($mode -eq 'dry') { '--dry-run' } else { '--apply' }
    $out = ".codex_tmp\investment_review_product_completion_v2\p5_final_runs\${scope}_${mode}.json"
    & $PY @common --scope $scope $flag --out $out
  }
}
```

V-999 逐项重跑 V-002、V-003、V-202、V-302、V-401、V-402、V-501、V-502，并将 C-MAP-001、C-ENG-001 至 C-REL-001 对照上述回执、O-006 和 post-checkpoint clean proof；结果为全部 pass，且 `production_released=false`。

五个 phase checkpoint：

1. `1f7372e feat(review): define product completion data semantics`
2. `53560d0 feat(review): add safe automatic trade sync and fee estimates`
3. `523eac6 feat(review): orchestrate real facts-only review runs`
4. `ef99cd9 feat(review): add traceable review web workflow`
5. 本文件所在 checkpoint：`test(review): close product completion candidate`

相对 source baseline 的精确 changed paths 共 33 个：

```text
.agents/skills/investment-review/SKILL.md
config/investment_review.portfolio.reviewed.json
docs/codex_tasks/investment_review_product_completion_v2/CONTRACT.md
docs/codex_tasks/investment_review_product_completion_v2/START_HERE.md
docs/playbooks/INVESTMENT_REVIEW_PRODUCT_COMPLETION.md
reports/investment_review/product_completion/PRODUCT_COMPLETION_READOUT.md
reports/investment_review/product_completion/validation_summary.json
src/investment_review/cli.py
src/investment_review/fee_estimation.py
src/investment_review/models.py
src/investment_review/portfolio_snapshot_adapter.py
src/investment_review/review_runner.py
src/investment_review/store.py
src/investment_review/sync_service.py
src/portfolio/cli.py
src/portfolio/frontend/src/app.css
src/portfolio/frontend/src/investment_review.js
src/portfolio/frontend/src/investment_review.test.js
src/portfolio/frontend/src/main.js
src/portfolio/investment_review_service.py
src/portfolio/review_integration.py
src/portfolio/web.py
src/portfolio/web_assets/app.css
src/portfolio/web_assets/app.js
tests/test_investment_review_fee_estimation.py
tests/test_investment_review_portfolio_snapshot_adapter.py
tests/test_investment_review_product_api.py
tests/test_investment_review_product_automation.py
tests/test_investment_review_product_e2e.py
tests/test_investment_review_product_store.py
tests/test_investment_review_review_runner.py
tests/test_investment_review_sync_service.py
tests/test_portfolio_tracker.py
```

## 已知缺口

- 历史 decision/link 为 0；不推断动机，真实复盘保持 unknown/unlinked。
- 正式历史 portfolio snapshot 为 0；上下文保持 missing/partial。
- 30 笔费用为 unknown；没有填入金额，仍可 append-only 纠正。
- sidecar 中保留 3 个早期 Windows path-length failed status event；修复后对应 run 当前头均为 terminal partial/succeeded，历史没有被删除。
- 人工产品验收尚未发生；本分支只是本地候选。

唯一下一步：人工审核本地候选及其明确显示的 partial/unknown；若接受，再单独授权发布动作。

完整机器可读证据见 `validation_summary.json`。P5 自身 commit hash 和 clean-tree 证明在 checkpoint 后写入 Git 忽略的 `.codex_tmp/investment_review_product_completion_v2/final_git_proof.json`，避免自引用修改。
