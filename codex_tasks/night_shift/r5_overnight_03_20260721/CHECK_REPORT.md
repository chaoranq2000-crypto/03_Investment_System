# Night02 复核与 Night03 设计结论

## 结论

用户报告的 Night02 终态与原任务合同在结构上完全一致：

- 原合同为 40 个 mission-level tasks；
- 原合同要求把 63 个 blocker occurrences 与 6 个 parent work orders
  展开为 69 项队列；
- 原合同明确 Mission 完成不等于长期研究 Goal 关闭；
- 原合同要求 0/63 在没有独立接受/执行收据时保持不变；
- 原合同禁止自动人审、canonical state、sample quality、P2、PR、merge 和 force push。

因此，`40/40 passed + mission delivered + Night03 69 项 + 0/63 resolved`
是一致状态，不构成“Mission 已完成但研究 Goal 也应完成”的矛盾。

## 本环境的核验边界

本环境无法直接读取用户 Windows 路径下的：

- `mission_completion_receipt.json`
- `morning_readout.md`
- `next_night_queue.yaml`

GitHub 最终提交页和动态 Actions 页面也未能稳定抓取。因此：

- `069da527452def6c59c3772750e933d8611ccadf`
- CI run `29681505920`
- `40/40`
- clean/no PR/local=remote
- 69 items、0/63

在本包中被标记为 **user-reported, runtime-hard-verified**，不是被我伪装成已独立读取的事实。

`bootstrap_worktree.ps1` 与 `tools/inspect_night02_outputs.py` 会在真实工作区中再次硬核验：
远端 SHA、物理收据、晨报、队列数量、CI、PR、clean 和历史 Bundle path diff。
任一不一致都阻止 Night03 开始。

## Night03 不再重复做什么

Night03 不再把主要时间投入：

- mission outcome 状态机；
- no-safe-pilot 修复；
- 基础 queue expander；
- 通用 crash/resume 框架；
- Night02 已完成的 40 项运行时加固。

## Night03 的主目标

Night03 解决 Night02 之后的真正瓶颈：

```text
69 项 occurrence queue 已准备
    ↓
但 evidence / analysis / human / pointer approval 尚未成为可信决定
    ↓
建立 exact-hash decision intake
    ↓
有批准就执行和解锁
无批准就生成不可变候选包并继续工程回归
    ↓
resolved 只由独立 receipt 增加
```

## 成功状态

Night03 允许两种诚实成功：

- `delivered_with_resolution_delta`：至少一个 occurrence 有合格 resolution receipt；
- `delivered_candidate_ready`：没有可消费的外部决定，但所有候选/交接/依赖矩阵和工程门已完成。

第二种状态仍必须写明 `0/63 resolved`，长期 Goal 继续开放。
