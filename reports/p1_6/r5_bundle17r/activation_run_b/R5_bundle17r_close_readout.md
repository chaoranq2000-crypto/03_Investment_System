# R5 Bundle 17R Activation Receipt Readout

- Baseline: `7ab395283f432faac7bbc0e83a0b0cf4976ed5dc`
- Run ID: `r5_bundle17r_activation_20260715_911136d_backflow`
- Generation ID: `activation_gen_r5_bundle17r_1fb1ea838a59cba3`
- Decision: `needs_targeted_backflow`
- Next stage: `R5_bundle17r_targeted_backflow`
- Cases passed: `0` / `4`
- Blockers: `63`
- Canonical workflow-state mutation: `false`
- Sample quality allowed: `false`
- P2 allowed: `false`

## Case matrix

| Case | Ticker | Engineering | Human review | Issue codes |
|---|---|---|---|---|
| golden_copper_foil_product_generation | 301217.SZ | BLOCKED | not_ready | ASSERTION_FAILED, ASSERTION_POINTER_UNRESOLVED |
| golden_crdmo_backlog_conversion | 603259.SH | BLOCKED | not_ready | ASSERTION_FAILED, ASSERTION_POINTER_UNRESOLVED |
| golden_gold_mining_cycle | 600988.SH | BLOCKED | not_ready | ASSERTION_FAILED, ASSERTION_POINTER_UNRESOLVED |
| golden_multi_business_ai_infrastructure | 600673.SH | BLOCKED | not_ready | ASSERTION_FAILED, ASSERTION_POINTER_UNRESOLVED |

## Targeted backflow

| Case | Code | Owner skill | Target stage | Requested action |
|---|---|---|---|---|
| suite | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| suite | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| suite | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| suite | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| suite | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| suite | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| suite | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| suite | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| suite | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| suite | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| suite | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_copper_foil_product_generation | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_copper_foil_product_generation | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_copper_foil_product_generation | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_copper_foil_product_generation | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_copper_foil_product_generation | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_copper_foil_product_generation | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_copper_foil_product_generation | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_copper_foil_product_generation | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_copper_foil_product_generation | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_copper_foil_product_generation | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_copper_foil_product_generation | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_copper_foil_product_generation | ASSERTION_POINTER_UNRESOLVED | quality-review | R5_bundle17r_targeted_backflow | bind the assertion to the exact field emitted by the upstream artifact |
| golden_copper_foil_product_generation | ASSERTION_POINTER_UNRESOLVED | quality-review | R5_bundle17r_targeted_backflow | bind the assertion to the exact field emitted by the upstream artifact |
| golden_crdmo_backlog_conversion | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_crdmo_backlog_conversion | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_crdmo_backlog_conversion | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_crdmo_backlog_conversion | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_crdmo_backlog_conversion | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_crdmo_backlog_conversion | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_crdmo_backlog_conversion | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_crdmo_backlog_conversion | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_crdmo_backlog_conversion | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_crdmo_backlog_conversion | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_crdmo_backlog_conversion | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_crdmo_backlog_conversion | ASSERTION_POINTER_UNRESOLVED | quality-review | R5_bundle17r_targeted_backflow | bind the assertion to the exact field emitted by the upstream artifact |
| golden_crdmo_backlog_conversion | ASSERTION_POINTER_UNRESOLVED | quality-review | R5_bundle17r_targeted_backflow | bind the assertion to the exact field emitted by the upstream artifact |
| golden_gold_mining_cycle | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_gold_mining_cycle | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_gold_mining_cycle | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_gold_mining_cycle | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_gold_mining_cycle | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_gold_mining_cycle | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_gold_mining_cycle | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_gold_mining_cycle | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_gold_mining_cycle | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_gold_mining_cycle | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_gold_mining_cycle | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_gold_mining_cycle | ASSERTION_POINTER_UNRESOLVED | quality-review | R5_bundle17r_targeted_backflow | bind the assertion to the exact field emitted by the upstream artifact |
| golden_gold_mining_cycle | ASSERTION_POINTER_UNRESOLVED | quality-review | R5_bundle17r_targeted_backflow | bind the assertion to the exact field emitted by the upstream artifact |
| golden_multi_business_ai_infrastructure | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_multi_business_ai_infrastructure | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_multi_business_ai_infrastructure | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_multi_business_ai_infrastructure | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_multi_business_ai_infrastructure | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_multi_business_ai_infrastructure | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_multi_business_ai_infrastructure | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_multi_business_ai_infrastructure | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_multi_business_ai_infrastructure | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_multi_business_ai_infrastructure | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_multi_business_ai_infrastructure | ASSERTION_FAILED | quality-review | R5_bundle17r_targeted_backflow | route the failed upstream gate to its owning stage; do not edit the expected value |
| golden_multi_business_ai_infrastructure | ASSERTION_POINTER_UNRESOLVED | quality-review | R5_bundle17r_targeted_backflow | bind the assertion to the exact field emitted by the upstream artifact |
| golden_multi_business_ai_infrastructure | ASSERTION_POINTER_UNRESOLVED | quality-review | R5_bundle17r_targeted_backflow | bind the assertion to the exact field emitted by the upstream artifact |

## Boundary

Bundle 17R binds and validates physical Bundle 16R, 15R, and 14R outputs and emits exact-hash review handoffs. It does not create evidence, alter upstream results, synthesize reviewer approval, mutate canonical state, or authorize sample quality/P2.
