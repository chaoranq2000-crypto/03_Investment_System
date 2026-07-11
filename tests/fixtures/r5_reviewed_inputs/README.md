# R5 reviewed-input test fixtures

These files are deterministic synthetic test data. They are not research evidence, do not describe a listed company and must never be copied into `data/reviewed_inputs/**`.

Fixture identity:

- workflow: `wf_fixture_r5_bundle4`
- stock code: `000000`
- evidence IDs: `ev_fixture_*`
- network access: disabled
- sample-quality and P2: always disabled

Scenarios:

- `accepted_core_complete`: accepted market, peer, forecast and valuation inputs; business disclosure absent.
- `accepted_all_complete`: all five readiness input types accepted, while fixture-mode caps remain false.
- `mixed_status`: accepted, accepted-degraded, pending and rejected decisions coexist; only accepted rows may activate full reviewed flags.
- `invalid_duplicate_input_id`: two otherwise valid rows share one `input_id`.
- `invalid_cross_workflow`: one row uses a different synthetic workflow.
- `invalid_cross_stock`: one row uses a different synthetic stock identifier.
- `invalid_template_as_evidence`: accepted rows are marked `template_only` or `not_evidence`.
- `invalid_folder_type_mismatch`: the row `input_type` disagrees with its parent directory.
- `invalid_missing_evidence`: retained legacy negative fixture for an accepted row without evidence.
- `invalid_accepted_todo`: retained legacy negative fixture for an accepted row carrying a critical TODO.
- `valid_pending` and `valid_accepted_degraded`: retained compatibility fixtures from the earlier dropzone contract.

Invalid identity scenarios intentionally contain one mismatching workflow or stock value. No fixture success may change the committed `wf_20260703_stock_first_002837_invic` run or open a real research gate.
