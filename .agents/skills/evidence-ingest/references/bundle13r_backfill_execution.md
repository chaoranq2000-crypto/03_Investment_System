# evidence-ingest — Bundle 13R reviewed backfill

Consume the Bundle 13R execution queue in dependency order. For each T1 item:

1. acquire or locate primary issuer/exchange evidence;
2. register immutable raw evidence and stable evidence IDs;
3. record page/table/paragraph locators;
4. classify the answer as `confirmed`, `bounded_estimate`, `missing` or `conflicting`;
5. record unit, period, confidence and financial mapping;
6. obtain human review before promotion.

Do not infer revenue from product existence, market size, delivery language or customer intention. Missing items must keep a dated replacement trigger.
