# Overnight Mission

## Mission ID

`r5_overnight_01_autonomous_harness_and_bf2_activation`

## 上层目标

推动 R5 从“工程回流基础设施可用”进入“样例级研究能力实证与生产化”阶段。第一夜不以强行消除 63 个阻断项为目标，而以建立一个能够连续、安全、可恢复地执行真实回流工作的最小运行时，并把现有 BF2 工作单变成可信队列为目标。

## 当前真实状态

- BF2 execution receipts 工程补丁已提交并推送；
- 真实 BF2 有 6 个工作单，全部 `pending`；
- 63 个 blocker occurrence 中已解决 0 个；
- 无 failed、orphan 或 rejected artifact；
- sample quality、P2 和 canonical state 均未开放；
- `.local/` 和 `reports/p1_6/r5_bundle17r_bf2*` 为本地未跟踪运行产物。

## 本夜工作流

```text
精确基线与只读输入盘点
    ↓
夜班任务合同与状态机
    ↓
运行锁、恢复与原子写入
    ↓
验收命令和 execution receipts
    ↓
BF2 六工作单 / 63 blocker 无损导入
    ↓
安全自动任务 pilot
    ↓
专项 + 全量 + 确定性回归
    ↓
提交、推送、晨报、下一夜队列
```

## 设计原则

1. **Codex session 是执行器，runner 是状态管理器。** 第一版 runner 不应依赖启动另一个 Codex 进程；它提供 validate/claim/start/complete/fail/block/resume/readout 等 CLI。
2. **状态必须可恢复。** 任务转换和回执写入采用临时文件 + 原子替换；进程崩溃后可从 `.local/night_shift/` 恢复。
3. **输入必须只读且有哈希。** 未跟踪 BF2 产物只能复制到 `.local/night_shift/inputs/` 或从绝对路径读取，不得纳入提交。
4. **阻断项身份不可丢失。** 保留 work_order_id、case_id、blocker_occurrence_id、source generation 和 suite 身份。
5. **自动化不能替代研究判断。** 没有证据就输出 `evidence_required`，没有人工决定就输出 `human_gate`。
6. **门禁不因工程成功而开放。** 夜班 harness 完成不等于 research-ready、sample-quality 或 P2。

## 推荐实现形态

```text
src/maintenance/night_shift/
  __init__.py
  models.py
  queue.py
  lock.py
  receipts.py
  bf2_seed.py
  runner.py

scripts/run_r5_night_shift.py
scripts/run_r5_night_shift.ps1
config/r5_night_shift.yaml
config/r5_night_shift_task_schema.json

tests/test_r5_night_shift_contract.py
tests/test_r5_night_shift_runner.py
tests/test_r5_night_shift_lock.py
tests/test_r5_night_shift_bf2_seed.py
tests/test_r5_night_shift_determinism.py
```

若仓库现有目录或命名契约要求不同，可在不创建新顶层目录的前提下适配，但必须在 ExecPlan 记录理由。

## 必须支持的任务生命周期

```text
pending
  → ready
  → claimed
  → running
  → passed
     failed_retryable
     failed_terminal
     dependency_blocked
     evidence_required
     human_gate
     skipped_cutoff
```

终态必须保存：完成时间、执行器、验收命令、退出码、回执路径、产物哈希、commit SHA 和 blocker 变化。

## 非目标

- 不建设完整 Symphony；
- 不自动调用外部交易系统；
- 不自动扩充公司池；
- 不抓取或伪造研究证据；
- 不自动生成人工审核通过；
- 不创建 PR、不合并 main；
- 不开放 canonical/sample-quality/P2；
- 不把六个 pending 工作单仅通过状态改写标为完成。

## 本夜退出门

全部满足才可写“Mission engineering complete”：

1. 运行时和 CLI 实现存在；
2. 新增测试通过；
3. 六工作单、63 blocker 导入计数精确；
4. BF2 seed 幂等，重复导入不新增重复任务；
5. `__suite__` 与 BF1 generation-lock 兼容测试通过；
6. safe pilot 已执行，或有 `no_safe_pilot` 证据；
7. 全量测试通过；
8. 确定性双跑逐字节一致；
9. 目标分支已推送；
10. 晨报真实记录研究门禁仍为 `needs_targeted_backflow`，除非真实 blocker 已按规则解决。
