# company-valuation — Bundle 12R 方法资格

`company-valuation` 必须消费 `R5_bundle12r_valuation_eligibility.yaml`。

- `peer_method.eligible=false`：禁止输出可信同业倍数中枢；
- `dcf_method.eligible=false`：禁止输出 DCF 结果；
- `sotp_method.eligible=false`：禁止输出 SOTP 结果；
- 失败时可继续使用反向估值与情景估值，并明确方法限制。

方法资格不能由 Reader 篇幅、自动质量总分或人工阅读流畅度抵消。
