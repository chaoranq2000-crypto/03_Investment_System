# ns01_t30_state_lock_resume — State, Lock, Resume

## Goal

保证夜班崩溃、重复唤醒或 Scheduled Task 轮询时不会并发破坏共享状态。

## Required behavior

- `.local/night_shift/run.lock` 单写者锁；
- lock 包含 run_id、pid、host、branch、started_at、heartbeat_at；
- stale lock 只能在明确超时且原进程不存在时恢复；
- queue state 采用 temp file + fsync/replace 原子写；
- 合法状态转换表；
- 06:15 Europe/London 后不得 claim 新任务；
- CLI 支持 `claim`、`start`、`complete`、`fail`、`block`、`resume`、`release-lock`。

## Tests

- double acquire rejected；
- stale recovery；
- illegal transition rejected；
- atomic write interruption；
- cutoff behavior。
