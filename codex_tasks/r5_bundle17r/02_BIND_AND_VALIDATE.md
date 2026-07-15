# 17R-2 — Bind physical results and validate activation

1. Create a real activation manifest from the supplied template outside committed source paths.
2. Record exact SHA-256 for every suite, lock, registered case contract and case artifact.
3. Keep the four case entries in the same order as Bundle 14R `qualification_results`, then bind policy-required assertions to exact JSON/YAML pointers.
4. Run the Bundle 17R CLI with `--fail-on-blockers`.
5. Inspect the activation receipt, case matrix and backflow queue.
6. Run again and require byte-identical outputs.
7. Any rerender or changed lock requires a new activation generation.
