# Contract Authority Policy

A task may execute repository mutations only when all of the following are true:

1. `allowed_paths` is non-empty, exact enough to enforce, and not a repository-wide wildcard.
2. `acceptance_commands` is non-empty and every command passes the trusted-command parser.
3. `contract_origin` identifies a human-reviewed package or a repository-owned deterministic generator.
4. `path_authority` and `acceptance_authority` are present.
5. The review packet hash matches `review_sha` when the task originated from a proposal.
6. The task passes pre-diff and post-diff scope checks.
7. Its dependencies are passed with stable receipts.

The proposal generator may suggest candidate files and tests, but it must emit `review_state: proposed`. It must never emit `approved`.

For the eight pointer occurrences in this package, the legacy artifacts prove that the desired fields are absent. Therefore the default resolution class is upstream generation/quality contract work, not a pointer substitution. Historical artifacts remain read-only.
