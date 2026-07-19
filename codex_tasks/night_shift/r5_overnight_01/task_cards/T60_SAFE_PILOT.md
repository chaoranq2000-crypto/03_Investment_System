# ns01_t60_safe_pilot — Safe Pilot

## Goal

证明夜班循环不仅能写基础设施，还能对一个真实、工程安全型任务完成 claim → implement → test → receipt → commit。

## Eligibility

必须同时满足：

- category = `engineering_local`；
- 不需要互联网新事实；
- 不需要人工 source mapping；
- 不修改 canonical/sample quality/P2；
- allowed paths 清晰；
- acceptance commands 可本地运行。

## No safe task path

如不存在 eligible task：

- 生成 `no_safe_pilot` receipt；
- 列出阻断原因分布；
- 生成下一夜任务建议；
- 不把此情况写成失败，也不虚构 resolved blocker。
