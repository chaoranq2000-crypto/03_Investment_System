# Night03 Morning Readout

- Mission outcome: `delivered_candidate_ready`
- Research resolution: `0/63`
- Candidate ready: `43`
- Dependency blocked: `20`
- Parent work orders pending: `6`
- Program Goal: `open_needs_targeted_backflow`
- Sample quality allowed: `false`
- P2 allowed: `false`

`delivered_candidate_ready` 只表示 Night03 工程交付完成，不表示研究计划完成。
候选包不是外部批准，也不是 resolution；只有 exact-hash 决定和独立 passed receipt 可以增加 resolved。

下一夜队列原样携带 `69` 个 unresolved ID，
并在 bootstrap 时从 post-push publication receipt 解析最终远端 HEAD。

账本校验：`0/63`。
