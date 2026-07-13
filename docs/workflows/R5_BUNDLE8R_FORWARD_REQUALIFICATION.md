# R5 Bundle 8R — a-stock-data capability adoption and forward evidence requalification

## Intent

Bundle 8R is a **forward requalification**, not a rollback. Bundle 9 and Bundle 10 outputs remain immutable historical artifacts. They are temporarily non-canonical because a new upstream evidence generation will be built. After Bundle 8R closes, Bundle 9R and Bundle 10R must be regenerated against the new generation lock.

```text
Bundle 8/9/10 historical close
        ↓ retain, do not delete
Bundle 8R capability + adapter + evidence requalification
        ↓ new evidence_generation_id
Bundle 9R forecast/valuation rebuild
        ↓ same generation_id required
Bundle 10R reader/quality rebuild
```

## Why this is required

The previous acquisition layer introduced routing, retry, source health and schema-drift handling, but a route entry did not prove that an adapter was live. A prominent example is `market_snapshot_pull`: it registers an externally supplied CSV and therefore must not be treated as a live mootdx or Tencent adapter.

## Operational definition

A capability is operational only when all of the following are present:

1. importable module or resolvable CLI entrypoint;
2. supported endpoint hint;
3. fixture test;
4. explicit live smoke receipt for network-capable adapters;
5. immutable raw archive;
6. evidence-manifest write;
7. schema fingerprint and drift test;
8. claim-boundary test;
9. independent failure-domain fallback for core capabilities.

A YAML route, planned adapter name or manually supplied snapshot does not satisfy this definition.

## Close boundary

Bundle 8R closes at the research-input layer. It must not edit the old Reader v3 to make the report look better. It must produce a new evidence generation lock and a research-question coverage matrix. Bundle 9R and 10R own downstream regeneration.
