# ExecPlan — R5 Overnight Mission 01

本文件是活文档。Codex 必须在执行过程中持续更新，不得只在结束时补写。

## Purpose

实现一个最小可用的夜班任务运行时，并将真实 BF2 工作单接入队列，为后续连续的研究定向回流建立可靠执行基础。

## Baseline

- Source branch: `codex/r5-bundle17r-bf2-execution-receipts`
- Expected source SHA: `36a801efc2bf0af10ad9702b8c6266ebf1935d6f`
- Target branch: `codex/r5-night01-autonomous-harness`
- Initial research gate: `needs_targeted_backflow`
- Initial BF2 truth: `6 pending work orders`, `0/63 resolved blockers`

## Plan

1. Baseline preflight and read-only local input manifest.
2. BF2 inventory and compatibility map.
3. Task contract, schema validation and queue loader.
4. Atomic state machine, lock and resume.
5. Acceptance command execution and receipts.
6. BF2 seed adapter and idempotency.
7. Safe pilot or explicit no-safe-pilot result.
8. Targeted, full and deterministic regression.
9. Morning readout, next-night queue, commit and push.

## Progress

- [x] `ns01_t00_preflight`
- [x] `ns01_t10_bf2_inventory`
- [x] `ns01_t20_contract_and_loader`
- [x] `ns01_t30_state_lock_resume`
- [x] `ns01_t40_acceptance_receipts`
- [x] `ns01_t50_bf2_seed_adapter`
- [x] `ns01_t60_safe_pilot`
- [x] `ns01_t70_regression_determinism`
- [x] `ns01_t80_readout_next_queue`
- [x] `ns01_t90_commit_push`

## Discoveries & Surprises

- 本地源分支、远端源分支和任务包基线三者均为
  `36a801efc2bf0af10ad9702b8c6266ebf1935d6f`。
- `C:\Projects\03_Investment_System_bf2` 仅保留任务包声明的未跟踪 BF2
  运行产物；未清理、未暂存、未修改。
- 隔离 worktree 已建立为 `C:\Projects\03_Investment_System_night01`，目标分支为
  `codex/r5-night01-autonomous-harness`。
- `bf2_execution_manifest.yaml` 明确指向 `source_bf1/run_a`，因此输入交接以
  `run_a` 为 BF1 合同源，并补充 EX1 fixed results 与 `run_verified_c` 真值摘要。
- 只读输入集含 33 个文件、172723 bytes，input-set SHA-256 为
  `eb1a608ebbedccd83889ca1d15485f69704bed7771a54e2a4e68d4b6b80bb60a`。
- BF1 CSV 用空字符串表示 suite case；EX1 fixed result 用 `case_id=__suite__`。
  夜班适配器必须保留源值并规范化为 `__suite__`，不能丢弃 suite work order。
- 现有 BF2 + EX1 专项基线为 `21 passed`。
- 任务包的 `tests/test_r5_night_shift*.py` 依赖 POSIX shell 通配符展开；Windows
  会把它作为字面量交给 pytest。验收命令已固定为 7 个明确测试文件，等价基线为
  `26 passed`。
- BF2 inventory 精确复算为 6 work orders、63 blocker occurrences、0 resolved、
  0 failed、0 orphan、0 rejected；suite aliases 和 BF1 generation-lock shape 均通过。
- occurrence 分类为 8 `engineering_local`、8 `evidence_required`、24
  `analysis_required`、3 `human_gate`、20 `dependency_blocked`。分类不改变解决计数。
- seed queue 共 69 tasks（63 occurrence + 6 parent work orders）；A/B queue、inventory、
  receipt 三组文件逐字节一致。
- 8 个 engineering-local occurrence 均缺少源合同 allowed paths 和 executable
  acceptance commands，因此本夜 `no_safe_pilot`，真实 blocker 变化仍为 0。
- source-route gate 为 `pass`（17 capabilities、0 blocking）；专项、全量、scope guard、
  seed determinism 和 readout determinism 全部通过。
- T90 可信命令链再次确认全库 `959 passed, 2 skipped`，并在报告层收口前确认
  本地与远端均为 `90172520bb437014240443a34505bc38a7a69c06`。
- 发布后用 `Get-FileHash` 重新读取原始 ZIP，确认完整 64 位 package SHA-256 为
  `d19ab2c9bcb811c63523b057f0e503be448e81568d0098917fef2d6e6918cd8c`；初版元数据
  少了末尾 `c`，已修正 preflight、baseline、delivery receipt 和派生 readout JSON，
  输入文件与 input-set SHA 未发生变化。

## Decision Log

| Time | Decision | Rationale | Consequence |
|---|---|---|---|
| 2026-07-19 01:05 BST | 从精确 BF2 SHA 创建独立 worktree 和新目标分支 | 任务包将 source SHA、target branch 和 isolation 定义为硬门禁 | 脏 `main` 与源 BF2 运行产物均未触碰 |
| 2026-07-19 01:14 BST | 只复制 Mission 实际消费的 BF1/EX1/verified-summary 输入 | 保持输入最小、只读、可哈希，不复制无关截图、ZIP 或历史 run 树 | `.local/night_shift/inputs/<sha>/` 保持 untracked |
| 2026-07-19 01:14 BST | 缺失的 work-order allowed paths 保持 unknown | BF1 合同未声明 allowed paths，禁止猜测 | safe pilot 只有在后续发现明确路径和命令时才可领取 |
| 2026-07-19 01:30 BST | 将 night-shift 通配符验收改为明确文件列表 | Windows 不展开 pytest 路径通配符 | 验收语义不变，命令可在本机和 CI 中复现 |
| 2026-07-19 01:40 BST | 对 8 个 pointer occurrence 走 `no_safe_pilot` | category 识别不能替代 allowed-path 与 acceptance 合同 | 生成阻断包，保留 6 pending / 0-of-63 resolved |
| 2026-07-19 01:54 BST | 关闭 T90 前先推送两个逻辑提交并核对远端 | delivery receipt 需要可验证的非自引用 SHA checkpoint | 本地与远端在 `90172520...` 一致，最终报告层另作普通提交 |
| 2026-07-19 02:10 BST | 下一夜队列保持 human/evidence/analysis gates 显式关闭 | 本夜没有新证据、研究判断或 exact-hash 人审授权 | 不自动开放 canonical、sample quality 或 P2 |
| 2026-07-19 02:20 BST | 发布后重算原始 ZIP 哈希并修正末位抄录 | 交付身份必须保留完整 64 位 SHA-256 | 只改元数据与确定性派生读数，重新走普通 push 和 CI |

## Validation Record

| Gate | Command | Result | Receipt |
|---|---|---|---|
| Targeted tests | `python -m pytest -q tests/test_r5_bundle17r_backflow_execution.py tests/test_r5_bundle17r_backflow_execution_cli.py tests/test_r5_bundle17r_backflow_execution_determinism.py tests/test_r5_bundle17r_backflow_execution_fail_closed.py tests/test_r5_bundle17r_verified_result_materializer.py tests/test_r5_bundle17r_verified_result_materializer_cli.py` | 21 passed | `.github/workflows/r5_bundle17r_bf2.yml`; `.github/workflows/r5_bundle17r_bf2_ex1.yml` |
| Source-route gate | `python scripts/run_source_route_quality_gate.py --import-check --output reports/quality/ci_source_route_quality_report.yaml` | pass; 17 capabilities; 0 blocking | `.github/workflows/ci.yml` |
| Full pytest | `python -m pytest -q` | 959 passed, 2 skipped | terminal run 2026-07-19 |
| Deterministic run A/B | `python scripts/run_r5_night_shift.py compare-files ...` | seed queue/inventory/receipt and morning readout/JSON/next queue A/B equal | `.local/night_shift/receipts/determinism.json`; `.local/night_shift/receipts/readout_determinism.json` |
| T90 delivery acceptance | trusted status/diff/full-pytest/SHA/ls-remote chain | passed; 959 passed, 2 skipped; local=remote | `.local/night_shift/receipts/ns01_t90_commit_push.json`; stable receipt `0e21f4ce39aa54c7e0c70b9c2c939959623cb7535bb9064e3cbf73f5d5aa2b6b` |

## Outcome

- 完成范围：preflight、BF2 inventory、contract/loader、state/lock/resume、acceptance
  receipts、BF2 seed、no-safe-pilot、专项/全量/确定性回归、10/10 晨报、下一夜队列、
  commit、push 和 delivery receipt。
- 未完成范围：无。后续 next-night 队列中的 human/evidence/analysis gates 不属于本任务包。
- 真实 blocker 变化：6 work orders 仍 pending；0/63 resolved；0 failed/orphan/rejected。
- 推送 checkpoint：`3234370782ca8295af8eba746fd597eea9a515e3`、
  `90172520bb437014240443a34505bc38a7a69c06`、
  `f89a3ab71fa8dbb43d004f01bd19b64111721e80`；最终元数据修正提交以目标分支 HEAD
  为准，在最终普通 push 后从本地与远端同时核验。
- Delivery receipt：`reports/p1_6/r5_night_shift/r5_overnight_01_20260719/delivery_receipt.md`。
- 当前门禁：`needs_targeted_backflow`；sample quality、canonical state、P2 均关闭。
- 下一夜最高优先级任务：人审 8 个 pointer occurrence 的 exact allowed paths 与
  acceptance commands；未审前不可自动领取。
- 需要人工决定：证据导入、研究分析、exact-hash review 和工程合同授权。
