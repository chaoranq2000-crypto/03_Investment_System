# V1 Governance Integration Cleanup Readout

## P1 — Blocker scope and degradation semantics

- State: complete at checkpoint `0906a5fa8c785da1a74326aa19dbf0abc58ddd2e`.
- Package: `docs/codex_tasks/v1_governance_integration_cleanup_v2`.
- Frozen contract SHA-256: `c160ea2d676d5ba9a9893070be1a6e4418193cc508db07e71dd48cd0394a642f`.
- Package setup checkpoint: `f41d99dc3685da6b1317da58b73beb23fc95135c`.
- Preflight: pass; dedicated worktree was clean, required remote refs matched, and the dirty user main worktree remains read-only.
- Baseline V-003 P1 result: 61 passed, 0 failed.
- Implemented `decision_semantics_version: current_goal_v1` for new or updated active state while preserving unmarked historical V1 states as explicit read-only compatibility.
- Implemented `impact_scope`, `active_disposition`, `affected_capabilities`, and `blocks_current_goal` in the workflow and quality issue contracts.
- Implemented deterministic `accepted`, `accepted_with_todos`, `needs_fix`, and `blocked` derivation. Severity is descriptive and cannot decide the outcome alone.
- Implemented the direct disclosure → audited aggregate → bounded estimate/scenario → unknown/omit degradation ladder.
- Removed Bundle11R–16R and R5-G1–R5-G11 from ordinary routing. Retained Bundle11/12/13 runtime modules are explicit-input, local-output evaluators and do not write workflow state.
- Preserved inactive legacy adapters in the P5 inventory instead of changing them outside the P1 allowlist.
- V-002: pass.
- V-003 P1: 90 passed.
- Compatibility tests: 63 passed.
- V-009: pass; no protected or out-of-scope path changed.

## P2 — Final-report-only human review

- State: complete at checkpoint `aa73859ddf8dbef2ad94b8c72dbf0ffc3931b851`.
- Phase parent: `0906a5fa8c785da1a74326aa19dbf0abc58ddd2e`.
- The only active human boundary is the final report. Its record binds a canonical report path, unique required/current artifact, machine-recomputed SHA-256, real reviewer, timezone-aware time, decision, notes, and conditional change scope.
- Automatic workflow outcome and `system_v1_complete` remain machine-derived. `not_requested|pending` do not block them. `sample_quality_ready=true` additionally requires a current `approved` report and all other applicable sample-quality conditions; approval is necessary, not sufficient.
- Report-byte changes invalidate prior human decisions. Replacing a committed human decision requires a strictly later event, including an approved → pending → approved sequence.
- `changes_requested` routes to `needs_fix` only when it reveals an automated-quality defect; report-only revision preserves the machine-quality outcome.
- Evidence, claim, metric, candidate, calculation, generation lock, and receipt hashes remain machine controls. Parallel human-review aliases are rejected.
- Historical Bundle/Night/Reader review artifacts, old Goal authorizations, and generation locks are read-only compatibility inputs and have exited active routing.
- Unmarked legacy V1 replay remains read-only compatible only while completion truth fields are absent or false; an unmarked truth claim is rejected.
- V-002: pass.
- V-003 P2: 178 passed.
- Compatibility tests: 75 passed.
- Adversarial review: no blocker.
- V-009: pass; 26 phase paths, all authorized, and the user main worktree status vector exactly matches preflight.

## P3 — 002837 official-disclosure policy refresh

- State: complete at checkpoint `6c7fc2a35942bb04f5ef0ecfa2c6ccbd10e0a069`.
- Phase parent: `aa73859ddf8dbef2ad94b8c72dbf0ffc3931b851`.
- New canonical run: `reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh`.
- The standalone runner reads only `data/manifests/evidence_manifest.csv` and the fixed annual/interim PDF plus processed-text pairs. It does not import the old replay, read a historical workflow directory, use network access, or overwrite raw data.
- The 2025 annual report PDF/text hashes resolve pages 15–16. The 2025 interim report PDF/text hashes resolve page 9.
- Room/cabinet revenue, revenue share, cost, and gross margin are preserved as direct disclosures. The 324,058-unit industry total is display-only and is not split across product lines.
- Line-level gross-profit amounts and gross-profit contribution percentages remain explicit `MISSING_DISCLOSURE`; gross-margin percentages are not reused as either field.
- The interim liquid-cooling revenue is represented as strictly greater than CNY 200,000,000 for 2025H1, not as an exact value.
- Room/liquid partial classification overlap is confirmed while its amount remains unknown. Cabinet/liquid remains unknown; neither overlap nor never-overlap is asserted.
- Four historical high issues are reclassified into new current issue IDs. They remain high/open and historically unresolved, but are visible, unused, scoped below workflow, and nonblocking.
- The current automatic status is derived as `accepted_with_todos`; all automatic gates pass except `G5=not_applicable`. Final-report review remains `not_requested`; all sample/P2/release truth fields remain false.
- V-003 P3: 194 passed.
- V-004: 16 passed; two unique temp outputs have semantic digest `2d8487beb46f10b6df103a9a2808998870a19556ef6879959ed15c6eb90cbcc6` and byte-identical 17-file trees.
- V-008: pass; 17 capabilities, 20 sources, zero blocking issues.
- V-009: pass; 26 phase paths, all authorized, with frozen sources and the user main worktree unchanged.

## P4 — Historical blocker policy migration

- State: complete at checkpoint `3741c807ae1d9859e8cb72d5e587a5bb74f2082e`.
- Phase parent: `6c7fc2a35942bb04f5ef0ecfa2c6ccbd10e0a069`.
- The protected source root map remains byte-identical to engineering source `f60f220ae252262a537c612ce193fc779901984b`: Git blob `526d9964a95ddc866fa960a1b9556e720ca80178`, content SHA-256 `39aadff44cf51d1ad5607d8ec8481bbab42650723eaf5a981415df0ee3facacf`.
- The active migration contains exactly seven root rows and no occurrence, parent, carry-forward or candidate-decision overlay. It preserves every historical root as open and all 63 historical occurrences as unresolved.
- `external_approval_and_independent_receipts_absent` is `policy_retired`; only the old intermediate human approval/decision/independent-receipt gate is retired. Current machine provenance, hashes and replay receipts remain required.
- `suite_exact_hash_review_pending` is `not_required_for_active_v1`; intermediate human hash decisions are not required, while hashes remain machine-integrity controls and only the final report hash may bind human review.
- `analyst_conclusions_pending` is a visible nonblocking section-level `report_limitation`; `reviewed_evidence_acceptance_absent` is a visible unused claim-level `unknown`. Their P3 references are current-policy examples, not historical-case resolution evidence.
- The three legacy Bundle16R–Bundle17R compatibility roots remain open `historical_backlog` with no canonical impact. They are not relabeled as repaired.
- Dynamic row reconciliation proves 63 occurrences, 20 dependency-blocked occurrences, 6 parents, 69 unique carry-forward nodes, 43 candidate-ready rows, 0 historical resolutions, 532 dependency edges and 6 valid duplicate references. All seven roots are covered once, with no orphan, duplicate ID or cycle.
- The disposition distribution is one `policy_retired`, one `not_required_for_active_v1`, one `report_limitation`, one `unknown`, three `historical_backlog` and zero `active_defect`. All seven have `blocks_current_goal=false`.
- P4 does not claim `system_v1_complete`; later engineering, cleanup and publication gates remain.
- P5 decoupled `tests/test_r5_v1_blocker_root_cause_map.py` from physical Night/Bundle files before the completed Night wave. The P4 validator reads only the retained root map, its durable Git blob, permanent policy files and retained P3 artifacts; v8 keeps that behavior unchanged.
- V-005: 18 passed.
- V-009: pass; 9 phase paths, all authorized, with the original root map, frozen sources and user main worktree unchanged.

## P5 — Historical runtime decoupling and ordered wave cleanup

- State: Night, Bundle and old002837 waves are completed and committed; all three contract-specified immediate post-wave regressions passed, but final all-wave V-010 failed. P5 is blocked before candidate sealing and publication.
- Package: `docs/codex_tasks/v1_governance_integration_cleanup_v8`; frozen contract SHA-256 `c8f19b03dd2fa17016bab3995eaa48fe8604bdb7e7027e5197aedcbfac01eb8b`.
- Package setup checkpoint: `37d312b00bfbad33bf66a7e1a3169a9fd0559ad8`, direct parent `fe986a0359c0268ac94eea696c3a4795403e4614`, containing only the v8 contract and start file. The parent is the exact-empty-directory root-policy checkpoint.
- The pre-delete decoupling claim was not fully proven. Final all-wave pytest exposed 10 retained tests that still read deleted Bundle/old002837 assets through called functions, YAML artifact paths, or default-value branches. No deleted path was restored.
- The three A.7 Night CI tests were converted from positive legacy-route requirements to equal-strength retirement assertions. They still require `fetch-depth: 0`, the source-route gate, the exact V-006 command, full `python -m pytest -q`, and the no-push/no-force boundary. They remain Night deletion targets.
- The retained Bundle capability dependency graph remains noncanonical, but the active reference scan's `reference_count=0` is a false negative: its AST rule does not follow candidate values across calls, YAML path payloads, or default branches into physical reads.
- The exact cleanup inventory contains 1,386 files and 9,787,412 content bytes. Its ordinal UTF-8 NUL path vector is 121,264 bytes with SHA-256 `974d45610144d616f69c3c368d9ea1a0a27d66601a24f748aa8148e2ee702f33`.
- Wave partition is Night 680 files / 4,480,614 bytes / path SHA-256 `1ec2f42b84c1078f6b26caa377e9c1fb3efff9221196bc2e02bd819588a59c59`; Bundle 205 / 1,770,109 / `fc8912dfe6d20d92bd8fe907d4400ae90b724826a7c468ba5286232dc3b3363a`; old002837 501 / 3,536,689 / `73d0a405b928fa3fa615d5b0d527f16f7c1182bb16239fb9ef89266d9868862f`.
- All three wave documents and file rows bind `deletion_actor=codex_exact_manifest_one_file_at_a_time` with authorization true. The destructive dispatcher rejects completed Night and accepts only the current newly armed v8 Bundle or old002837 wave.
- The old002837 post-file directory manifest is fixed at 29 deepest-first paths: relative NUL vector 2,208 bytes / `1e987f07ab4aa9b7c54a7444b053949b5c5d377655903d9715d8948e42446cd3`; dedicated-worktree absolute NUL vector 3,803 bytes / `31669a8f873c2510709a7f9828b27dad4eab9fe49a159071d40345693e770b75`.
- Night clean arm was `e3b7ac48b784749e32252faf543c8d9ab796d830`. The Codex exact-file surface removed the 680 ordinal Night paths and commit `be42857bf88223e01c71e4a4dfbac8e3a47080aa` contains exactly those 680 deletions plus `manual_deletion_wave_night.yaml`.
- Bundle clean v8 arm was `b120a805736a89b5c6a0406e15d5a0d040a0f341`. The Codex exact-file surface removed the 205 ordinal Bundle paths and commit `274d47ec299a42946bc3b83f7908257e80f0f99b` contains exactly those 205 deletions plus `manual_deletion_wave_bundle.yaml`; old002837 501 paths remained present.
- old002837 clean v8 arm was `196797dbc0668652be66c9a65ce09a2ebc119b8b`. The Codex exact-file surface removed the 501 ordinal file paths; only after the complete raw vectors passed, the exact-directory surface removed 29 empty/non-reparse directories deepest-first and left the old run root absent. Commit `b5ebdbfe6ddce7698a438bc8afa69cf5a1c8fbd2` contains exactly the 501 file deletions plus `manual_deletion_wave_old002837.yaml`.
- Every manifest row is bound to a durable baseline commit, blob OID, byte count, content SHA-256 and restore command. The v8 independent restore recovered all 1,386 files and 9,787,412 bytes byte-for-byte under `C:\Users\Q\AppData\Local\Temp\v8_v1_historical_restore_e7939036de974f27afb7306970f49576`.
- Windows paths longer than 260 characters are handled only at the filesystem I/O boundary with extended-length paths; safety resolution, repo-escape checks, manifests and receipts keep normal paths. Unsafe in-repo restore roots and tampered hashes remain fail-closed.
- In v7, the authorized deterministic root receipt is byte-identical to the unchanged validator rendering (4,013 bytes; SHA-256 `f81fd3bf40bfc953e90df585188510f2d8382fd2a8b364fece93d6ae7190e5e4`). V-005 passed 18; V-006 passed 26 in 666.15 seconds; the independent control-plane validator returned `decision=pass files=1386 active_references=0`.
- For v8 A.2, V-002 passed; V-003 final passed 194; two V-004 runs produced the same semantic digest and its test passed 16; V-005 passed 18; V-006 passed 28; V-008 passed with 17 capabilities and zero blockers; V-011 returned `ok=true`, `state=running`, zero warnings.
- The pre-delete full repository pytest passed `1146 passed, 2 skipped` in 700.39 seconds while Bundle/old002837 assets still existed. It is not final deletion proof. The two skips remain the unchanged live-adapter manual smokes already present at `f60f220...`.
- After the Night deletion commit, V-006 passed `26 passed in 663.32s` and V-003 final passed `194 passed in 24.28s`; the worktree remained clean and the deleted Night paths were not recreated.
- After the Bundle deletion commit, V-006 passed `28 passed in 592.82s` and V-003 final passed `194 passed in 23.40s`; the worktree remained clean, Night/Bundle paths were not recreated, and all 501 old002837 files remained present.
- After the old002837 deletion commit, V-006 passed `28 passed in 611.71s` and V-003 final passed `194 passed in 23.41s`; all 1,386 wave files, all 29 old002837 directories and the exact old run root remained absent, and the worktree stayed clean.
- Final all-wave V-010 failed `10 failed, 966 passed, 2 skipped in 683.95s`; the same exact 10 tests failed again in 2.70 seconds. Failures are missing historical inputs, not deletion-vector drift. Seven failing test files are in A.1 but frozen v8 made completed A.1 decoupling read-only; `tests/test_r5_bundle8b_close.py` and the newly proven required implementation `scripts/validate_r5_bundle10r_human_review.py` are outside all A.1–A.7 sets.
- Independent quality audit passed: all changed paths were in A.1/A.2/A.7, no deletion or untracked path existed, each changed test retained or increased assertions, A.7 assertion counts increased from 6/3/3 to 13/13/13, and all 13+37+1 fixed-reader triplets matched.
- User main worktree remains read-only at HEAD `a345fafb522300831ed4206d35fa17f44570cb1f`; full status is 130 records / 9,156 bytes / SHA-256 `1b21ac246cb2ad4b055f5a264503fb1fad8fe9edae153e25c9cd6d19d4a719c0`, tracked-only is 20 records / 1,025 bytes / `3ab441f68037823866029eb2136149a807f6382755966daf96d33a85b965609b`.
- Next controlled action is user approval of a minimal v9 authorization amendment that reopens only the exact failing tests, the exact runtime path-resolution fixes proven necessary, and V-006 false-negative coverage. All three deletion manifests, deletion commits, wave order, absence state, restore proof and publication protocol remain unchanged. No seal or publication is authorized while V-010 fails.

### v10 controlled stage closure

- Package: `docs/codex_tasks/v1_governance_integration_cleanup_v10`; frozen SHA-256 `f7715de5429b961a34eca9c62fa3609682f8bdd5783900f3a830d81763e568ec`.
- Package-only setup commit: `1b0298da4513147830b359aaf3fa3f5a8c0f7371`, direct parent `696ca4cdf54858f9e259bb19fdd6349cd3cf2d6d`.
- Route-closure commit: `0d0e2cfeee55dbdc18bd519d9aed0cc703dd466c`. It replaced active default/canonical/worktree routing with explicit inputs or output roots and strengthened the scanner without changing research facts or completion semantics.
- The strengthened active-root audit moved from 27 references across 12 paths to zero references and zero unknown classifications. Focused original regressions passed 13; route/behavior suites passed 62; the explicit-root subset passed 36.
- A.10 found no retirement-only candidate. `extended_wave_count=0`; no new cleanup manifest was created and no v10 deletion was performed.
- V-002 passed. V-003 final passed 194. Two V-004 runs remained semantically and byte-tree deterministic and its test passed 16. V-005 passed 18. V-006 passed 29 and restored all 1,386 files / 9,787,412 bytes byte-for-byte in an external temporary root. V-008 passed with 17 capabilities and zero blockers.
- Final dedicated-worktree pytest passed `977 passed, 2 skipped in 781.84s`; both skips are unchanged opt-in live-adapter manual smokes already present at `f60f220...`.
- Before and after validation, all 1,386 completed-wave files, all 29 directories and the exact old run root remained absent. The three historical manifests, receipts, commits and vectors remain unchanged.
- User main worktree remains read-only at `a345fafb522300831ed4206d35fa17f44570cb1f` and exactly matches the authorized full/tracked status vectors.
- The first two clean-clone attempts under the shared or unique Temp parent were rejected because the protection test requires the checkout and real dirty main tree to share `C:\Projects` as their parent. They are environment-topology failures, not candidate regressions.
- The final independent `--no-local` clone at `C:\Projects\v10_clean_checkout_e5d2592c15724999b727327886155c9c` has its own `.git`, checked out `8957416bf04434dc3d079a3ca9a2af49125e40d4`, was clean before and after testing, and passed `977 passed, 2 skipped in 707.55s`.
- Sixteen exact historical Bundle16R YAML/Markdown snapshots have CRLF blobs despite the repository LF default. A path-specific `.gitattributes` exception preserves their bytes and makes Windows clean checkout status deterministic without altering snapshot content or hashes.
- Remote preflight still matches frozen main `a345faf...`, Night05 `a96c1b...`, V1 source `f60f220...`; the execution ref is absent and there is no matching PR. Sealed candidate publication remains pending under mode A, and no external result will be written back after seal.

Later phases append their own sections. Publication evidence is never written here after the sealed candidate commit.

### v11 portable frozen-receipt repair

- v10 sealed candidate `bcb535618367024eb85f8bee7abb8419c56d75eb` remains immutable failed ancestry. Its exact-head push CI run `30257647025` failed only the two V-006 paths that rebuilt the fixed Windows absolute directory receipt with mixed separators on Linux; no PR or merge was created.
- v11 frozen contract SHA-256 is `68028d41f366d535daf7647faa8aae408e167f5442a96ed2ff7a3c3aeca18aae`; package-only setup `718d6630c861866b51ccec47787d3f4e146edc43` is a direct child of `bcb5356...`.
- Repair checkpoint `f7ed76377594f789d4f9d1dadae6150abae179be` uses `PureWindowsPath` only while reconstructing the fixed receipt. Runtime deletion containment continues to use the unchanged dedicated-root `Path.resolve(strict=True)` checks.
- A new POSIX path-flavour regression reproduced the exact pre-fix SHA drift and passed after repair. V-006 passed 30. The committed 29-row relative and absolute paths, 2208/3803 byte counts and both SHA-256 values remain unchanged.
- V-002 passed; V-003 passed 194; V-004 produced identical semantic/tree digests and passed 16; V-005 passed 18; V-008 passed with 17 capabilities and zero blockers.
- Dedicated-worktree full pytest passed `978 passed, 2 skipped in 743.29s`. Independent same-parent `--no-local` clone at `C:\Projects\v11_clean_checkout_c94b56f5d76040d4bc7d1347f9145cf8` passed `978 passed, 2 skipped in 730.76s` and remained clean.
- v11 performed no deletion. All 1,386 files, 29 directories and the old root remain absent; immutable manifests/receipts and the dirty user main status vectors are unchanged.
- Remote main/Night05/V1 source refs remain frozen; execution ref remains the failed candidate `bcb5356...`, with zero matching PRs. A new sealed candidate and publication mode A remain pending.
