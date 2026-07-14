# R5 Bundle 11R — Runtime operating-research refactor

## Position

Bundle 10R repaired generation binding, generic rendering, traceability, deterministic locks, and truthful human-review handoff. Bundle 11R moves upstream: it implements business-line economic archetypes, evidence questions, operating-driver calculation, peer eligibility, semantic quality, and issue backflow.

The global T0–T10 workflow remains the only kernel. Bundle 11R is an inner report-production loop, not a parallel workflow.

## Runtime chain

```text
business scope
  -> economic archetype assignment
  -> research-question matrix
  -> evidence status and bounded unknowns
  -> segment operating-driver equations
  -> consolidated revenue/gross-profit/finance bridge
  -> peer eligibility and valuation method qualification
  -> semantic research gate
  -> issue-to-stage backflow
  -> Reader render only after the input generation is qualified
```

## Core commands

```bash
python scripts/audit_r5_bundle11r_target.py --repo-root . --strict

python scripts/run_r5_bundle11r_runtime.py \
  --segment-plan templates/r5_segment_driver_plan.example.yaml \
  --evidence-status templates/r5_evidence_status.example.yaml \
  --peer-pack templates/r5_peer_pack.example.yaml \
  --semantic-payload templates/r5_semantic_payload.example.yaml \
  --output /tmp/r5_bundle11r_runtime_result.yaml
```

The example intentionally retains missing operating evidence and therefore returns research backflow. It is a control fixture, not issuer evidence.

## Close boundary

A runtime pass does not authorize sample quality or P2. Human review remains pending and must bind to the exact final Reader hash.
