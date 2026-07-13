# a-stock-data V3.4.0 full-capability review

Reviewed upstream: `simonlin1212/a-stock-data`, V3.4.0, commit `9ed665c`, reviewed 2026-07-13.

The upstream project declares ten layers, forty primary endpoint groups and three independent fallbacks. The normalized 43-record catalog is stored at `config/a_stock_data_capability_catalog.yaml`.

This patch does not copy upstream endpoint code. It adopts the following engineering methods with attribution:

- source priority based on failure domain and blocking risk;
- serial public-HTTP acquisition, session reuse, minimum interval and jitter;
- no immediate retry for permission/contract failures;
- schema-drift detection and explicit quarantine;
- independent fallback rather than another endpoint behind the same risk surface;
- endpoint-specific field tests;
- source-quality limitations, including unreliable or changed fields;
- official sources for announcements and other material claims.

License: Apache-2.0. Any future direct code reuse must retain license and attribution notices and identify local modifications.
