# ns01_t20_contract_and_loader — Contract and Queue Loader

## Goal

实现简单、类型清晰、确定性的夜班任务合同和队列加载器。

## Required behavior

- 标准库优先，Python 3.11+；
- 严格校验必填字段、状态和依赖；
- 拒绝重复 task ID、循环依赖和未知依赖；
- deterministic ordering 和 serialization；
- CLI 至少支持 `validate`、`list-ready`、`show`；
- 错误消息包含 task ID 和字段路径。

## Tests

- valid queue；
- duplicate ID；
- unknown dependency；
- cycle；
- invalid status；
- stable serialization；
- cutoff-aware ready selection。
