# 17R-3 — Human handoff and conservative close

- Confirm every passing case has a `pending` exact-hash handoff.
- Confirm blocked cases are `not_ready`.
- Automated jobs must not fill reviewer, timestamp or acceptance.
- Keep canonical workflow-state mutation, sample quality and P2 false.
- If all four cases pass, route to `R5_bundle18r_exact_hash_human_review`.
- Otherwise route every blocker to its recorded owner/stage and remain in Bundle 17R backflow.
- Stage only the declared implementation paths; generated outputs remain local unless a later reviewed promotion explicitly selects them.
