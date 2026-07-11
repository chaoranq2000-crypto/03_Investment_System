# R5 After Bundle 4 — Bundle 5 Status Baseline Readout

status: accepted_with_todos

## baseline_decision

- reviewed_on: `2026-07-11`
- base_commit: `aeb846b1f5eb39d1f29cd5a1fc88a35fbb06f017`
- base_state: `R5_REVIEWED_INPUT_FIXTURE_PROMOTION_SMOKE_PASSED`
- real_workflow: `wf_20260703_stock_first_002837_invic`
- real_002837_reviewed_inputs_supplied: `false`
- real_002837_reviewed_input_pilot_allowed: `false`
- canonical_registry_write_allowed_before_card_5_5: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`
- card_5_1_inventory_allowed: `true`

本卡只同步事实、建立 Bundle 5 expected-artifact manifest 和稳定文档入口。它不创建 reviewed input、不写 canonical registry、不改变真实 pilot/render gate，也不把样例报告或夹具视为研究证据。

## documentation_pointer

- README 继续把 P1.6 作为项目总阶段标签。
- 当前 R5 Bundle、gate 和允许产出级别只由 `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md` 中最新 canonical close readout 指向；README 不成为第二个运行时状态事实源。
- README 未硬编码 Bundle 5 为已完成或当前 gate 已开放。

## expected_artifact_contract

- `config/r5_bundle5_expected_artifacts.yaml` 声明 base state、target/partial/rollback 状态、五类核心输入、一类可选输入、Cards 5.0–5.8 的 producer ownership 和 reused checks。
- `owned_artifacts` 每个物理路径仅有一个 producer；跨卡复用放在 `reused_checks` 或 `shared_updates`，不伪装成重复所有权。
- `baseline_required_paths` 共 20 个路径；本卡要求它们全部物理存在。后续 planned artifact 由各自 `required_by_card` 和 Card 5.8 close test 收口，不提前生成空占位文件。
- Card 5.5 是第一个且唯一声明 `canonical_registries` 写入范围的 card；Cards 5.0–5.4 均为 `canonical_registry_write_allowed: false`。

## ci_warning_todos

- warning_id: `node20_action_runtime_migration`; severity: `low`; status: `open_non_blocking`; owner: `repository_maintainer`; next_action: 在不减少 Python compile 和 full pytest 语义的前提下验证 action 升级。
- warning_id: `conda_defaults_channel_implicit`; severity: `low`; status: `open_non_blocking`; owner: `repository_maintainer`; next_action: 环境兼容性核对后决定显式加入 `defaults` 或设置 `conda-remove-defaults`。
- 本卡不修改 `.github/workflows/ci.yml`；当前 CI 仍执行全部 tracked Python 编译和 `python -m pytest -q`。

## files_added

- `config/r5_bundle5_expected_artifacts.yaml`
- `tests/test_r5_bundle5_status_baseline.py`
- `reports/p1_6/R5_AFTER_BUNDLE4_STATUS_BASELINE_READOUT.md`

## files_modified

- `README.md`
- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md`

## commands_run

- `git status --short`
- `git diff --check`
- `.\\.conda\\investment-system\\python.exe -c "import yaml; from pathlib import Path; p=Path('config/r5_bundle5_expected_artifacts.yaml'); d=yaml.safe_load(p.read_text(encoding='utf-8')); assert isinstance(d, dict); print('bundle5_manifest_parse=pass')"`
- `.\\.conda\\investment-system\\python.exe -m pytest -q tests/test_r5_bundle5_status_baseline.py --tb=short -p no:cacheprovider`
- `.\\.conda\\investment-system\\python.exe scripts/check_r5_readout_truthfulness.py --rules config/r5_readout_truthfulness_rules.yaml --glob 'reports/p1_6/R5_AFTER_BUNDLE4_STATUS_BASELINE_READOUT.md' --strict --json $env:TEMP/r5_bundle5_status_baseline_truthfulness.json`

## exit_code

- pre-card git status / diff check: `0`
- expected-artifact YAML parse: `0`
- focused baseline pytest: `0`
- baseline truthfulness: `0`
- final git diff check: `0`

## stdout_or_stderr_summary

- YAML: `bundle5_manifest_parse=pass`。
- focused pytest: `6 passed`。
- truthfulness: `truthfulness_status=pass checked=1 failed=0`。
- git diff check: 无 whitespace error；README 仅有 CRLF/LF 工作区提示。
- CI 语义检查：compile 与 full pytest 命令均仍存在；两条 warning 作为 non-blocking TODO 保留。

## artifact_evidence

- inventory_status: `pass`
- baseline_required_paths: `checked=20 missing=0`
- producer_ownership: `duplicate_owned_paths=0`
- first_canonical_registry_writer: `card_5_5`
- package_sha256: `57691F7A7174224172448F6626120384E1F262AF09B92612C41DED72D39077BC`
- forbidden_scope_diff: Card 5.0 未修改 `data/reviewed_inputs/**`、`data/raw/**`、`data/processed/**`、`data/manifests/**`、真实 workflow registry/gate/render 产物或 `.github/workflows/ci.yml`。

## blockers

- none for entering Card 5.1 inventory and provenance review.
- no authority is granted for accepted status or canonical registry writes.

## known_todos

- 五类核心真实 input 的物理存在性、evidence anchor、reviewer、reviewed_at、freshness、limitations 和 conflict 状态须由 Card 5.1 fresh 清点。
- `node20_action_runtime_migration` 保持 non-blocking TODO。
- `conda_defaults_channel_implicit` 保持 non-blocking TODO。
- 根目录补丁包归档/跟踪策略由维护者另行处理，不纳入 Bundle 5 研究输入。

## next_card

- `R5_BUNDLE_5_1_REAL_INPUT_INVENTORY_AND_PROVENANCE_MATRIX.md`

## next_recommended_patch

- Bundle 5.1 real-input inventory and provenance matrix；若真实文件为 0 或核心 source-gapped，则产出请求队列并按任务卡停止。
