# R5 Evidence Request Queue Contract

status: `contract`

This queue turns visible R5 source gaps into planned evidence requests. It is a
local planning artifact only: builders and validators must not download files,
call live APIs, or convert missing inputs into facts.

Each request must include:

- `request_id`
- `workflow_id`
- `stock_code`
- `source_gap_id`
- `pack_section`
- `evidence_need`
- `source_type`
- `source_rank`
- `freshness_policy`
- `required_for_pack`
- `allowed_usage`
- `owner_skill`
- `status: planned`
- `evidence_id: null`
- `missing_reason`
- `next_action`
- `no_live_api: true`

Allowed usage must stay conservative until reviewed evidence is registered.
Requests can support facts, metric candidates, valuation context, peer context,
management comments, or clue-only follow-up, but they cannot create trading
instructions or sample-quality report permission by themselves.
