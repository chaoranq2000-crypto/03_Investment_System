---
name: portfolio-tracker
description: Maintain the repo-local private portfolio ledger from holding screenshots, broker CSV/XLSX statements, closing prices, qfq daily K-line and raw single-day minute observations, cycle-scoped operation markers, source-labeled equity industries, ETF-holdings-driven industry classifications, and completed clearance-cycle P&L. Use for opening snapshots, statement reconciliation, cost/P&L refreshes, factual daily/intraday chart review, closed-position returns, industry perspective, ETF constituent classification, and portfolio audits. This is a standalone utility skill and must never route through or mutate the research-orchestrator workflow.
---

# Portfolio Tracker

Operate `src/portfolio/` as a private accounting utility. Keep all user holdings and broker exports in ignored `data/db/` files.

## Hard boundary

- Do not call, edit, resume, or close `research-orchestrator`.
- Do not write `reports/workflow_runs/`, evidence manifests, research claims, readiness gates, watchlists, or P2 artifacts.
- Do not emit trading advice, target positions, or buy/sell/hold instructions.
- Do not commit `data/db/*.sqlite3`, holding CSVs, broker CSV/XLSX files, account identifiers, or screenshots.
- Use this skill only for portfolio bookkeeping, price refreshes, and audit output.

Read `docs/playbooks/PORTFOLIO_TRACKER.md` when field aliases, formulas, or CLI details are needed.

## Runtime

Run commands from the repository root with:

```powershell
.\.conda\investment-system\python.exe -m src.portfolio <command>
```

Default database: `data/db/portfolio.sqlite3`.

## Workflow

1. Inspect `git status --short` and preserve unrelated work.
2. Inspect every supplied image with the image viewer. Transcribe date, time, code/name, side, quantity, price, fee, amount, closing price, market value, cost, and P&L exactly as shown.
3. Validate arithmetic before writing:
   - buy occurrence amount = price × quantity + fee;
   - sell net amount = price × quantity - fee;
   - holding market value = close × quantity;
   - holding total cost = market value - unrealized P&L.
4. Resolve six-digit codes to Tushare codes. Prefer existing instrument records; otherwise verify through the configured Tushare client. Never guess an ambiguous name/code mapping.
5. Classify each statement relative to the opening baseline:
   - after baseline: preview and then apply as a real ledger entry;
   - on/before baseline: do not infer inclusion from the date alone. Use `--included-in-opening` only when the user explicitly confirms the snapshot already includes the trade, or the snapshot quantity/cost arithmetic proves inclusion;
   - complete historical clearance before the baseline: use `--historical-closed` only when the supplied batch independently starts from zero, never oversells, and ends at zero. Its cycles belong in clearance review, while its P&L must stay outside `realized_pnl_since_baseline`;
   - if the user confirms that a later-supplied trade was omitted from the snapshot, move the accounting baseline to before the earliest omitted trade and replay it as a real ledger entry, even when the screenshot was submitted on a later date;
   - unclear: keep it un-applied and report the exact ambiguity. Never treat the date the user supplied a screenshot as its accounting cutoff without evidence.
6. Refresh latest available closing prices and industry classifications, render the CLI or local dashboard, and verify totals and affected securities. Refresh daily K-line or single-day minute data only when the user explicitly clicks the corresponding update control, clicks a daily candle, enters/selects a ledger BUY/SELL date in the intraday view, or runs `refresh-kline` / `refresh-intraday`; opening a drawer, switching daily ranges, and selecting a non-trade date must remain cache-only. Never batch-refresh every trade date in a cycle. Before classifying any ETF, read `references/etf_industry_classification.md` and use disclosed constituents rather than its name as the primary evidence. When the dashboard is on the latest view, also verify the non-persistent intraday quote overlay and its source/time labels.
7. When sell entries reduce a security to zero, verify the completed clearance cycle: released moving-average cost, net sale proceeds, cycle cash income/fees, realized P&L, and return percentage. Never label a still-open partial sale as a completed clearance.
8. Run `tests/test_portfolio_tracker.py` and `tests/test_portfolio_web.py`, then check that private files remain ignored.

## Holding screenshots

Before the opening snapshot has been imported, consolidate corrections in an ignored file such as `data/db/portfolio_opening_YYYY-MM-DD.csv`, then import once:

```powershell
.\.conda\investment-system\python.exe -m src.portfolio import-opening `
  --input data\db\portfolio_opening_YYYY-MM-DD.csv
```

Prefer exact `total_cost = market_value - unrealized_pnl` over a rounded displayed cost price. Retain the displayed cost price only as a cross-check.

Record two dates separately: the accounting cutoff represented by the holdings and the date/time the screenshot was supplied. The submission date does not prove that earlier-dated statements are included. Before marking any statement `included_in_opening`, reconcile `snapshot quantity = pre-trade quantity + buys - sells` and the corresponding cost movement, and retain the user's explicit inclusion/exclusion statement.

If omitted pre-baseline trades are discovered later, rebuild in a shadow database: set the accounting baseline before the earliest omitted trade, import the corrected opening quantities/costs, replay all statements chronologically, preserve market-price observation dates and industry metadata, compare every unaffected position, then replace the live database only after validation and a backup. Do not relabel a later market observation as an earlier price.

If the database already has an opening snapshot, do not invent trades to force a corrected quantity or cost. Use an explicit audited correction mechanism if one exists; otherwise stop and explain that a rebaseline/correction feature is required.

## Broker statements

Always preview a post-baseline file first:

```powershell
.\.conda\investment-system\python.exe -m src.portfolio import-statement `
  --input C:\path\to\statement.xlsx --broker broker_label
```

Apply only after the preview has zero errors:

```powershell
.\.conda\investment-system\python.exe -m src.portfolio import-statement `
  --input C:\path\to\statement.xlsx --broker broker_label --apply
```

For old statements explicitly confirmed as already included in the opening snapshot, preview and apply with both `--included-in-opening` and `--apply`. Confirm afterward with `reconciliations`; these records must not change quantity or cost. Date ordering by itself is never sufficient evidence of inclusion.

For complete pre-baseline clearance histories that were not part of the opening position, preview and apply with `--historical-closed`. The batch must be self-contained from zero quantity back to zero quantity, and current positions plus all baseline-scoped summary fields must remain identical before and after import.

Reject or leave explicit TODOs for financing/margin trades, stock dividends, splits, external transfers, and other events whose cost basis is not determined by the supplied evidence. A transfer between two user-owned broker accounts may be recorded in `internal_transfer_reconciliations` only after both sides' security and quantity evidence matches; it must not create `BUY` / `SELL` ledger entries or realized P&L.

## Prices and verification

```powershell
.\.conda\investment-system\python.exe -m src.portfolio refresh-prices
.\.conda\investment-system\python.exe -m src.portfolio refresh-kline --code 600000.SH --range 3m
.\.conda\investment-system\python.exe -m src.portfolio refresh-intraday --code 600000.SH --date 2026-07-14
.\.conda\investment-system\python.exe -m src.portfolio refresh-industries
.\.conda\investment-system\python.exe -m src.portfolio show
.\.conda\investment-system\python.exe -m src.portfolio closed
.\.conda\investment-system\python.exe -m src.portfolio web
.\.conda\investment-system\python.exe -m src.portfolio ledger
.\.conda\investment-system\python.exe -m src.portfolio reconciliations
.\.conda\investment-system\python.exe -m src.portfolio transfers
```

Report the closing date actually returned by Tushare. Distinguish a successful core Tushare call from endpoint-specific permission failures. If any security is missing a price, do not present portfolio totals as complete.

The dashboard must stay loopback-only. It may read the same private ledger and invoke the existing price refresh command, but it must not add research-workflow routes, manifests, reports, or orchestration side effects.

K-line review is factual bookkeeping output. Store raw Tushare daily bars and adjustment-factor observations append-only, derive qfq prices at read time, and never display raw prices under a qfq label. Plot only `OPENING`, `BUY`, and `SELL` from the selected ledger cycle. Keep the original trade price, adjusted marker price, quantities, fees, source rows, missing factors, and mapping status visible; do not add technical signals or advice.

Single-day minute review is also factual bookkeeping output. Prefer Tushare `stk_mins` / `etf_mins` 1-minute data, and fall back to unadjusted BaoStock 5-minute data only after a sanitized, visible upstream failure. Persist validated minute observations append-only and read the latest observation for each interval end. Plot only ledger-cycle `BUY` / `SELL`, map a timestamped trade to the first interval end not earlier than the trade within the same session, keep BUY and SELL separate, and use the actual unadjusted weighted execution price as the marker value. Missing time, lunch/out-of-session time, and missing bars must remain unlocated; never infer a time or convert `OPENING` / `included_in_opening` observations into intraday trades. Indicators and cumulative average are historical display derivatives, not trading signals.

Daily-candle navigation may refresh a displayed pre-opening or post-close context date as long as it is not later than `as_of`. Keep the selected ledger cycle for operation isolation; context dates must return no invented trade markers.

### Intraday dashboard quotes

- The latest dashboard view refreshes intraday quotes every 60 seconds while the page is visible. Historical `as_of` views never use intraday quotes.
- Use the source order validated from the upstream `simonlin1212/a-stock-data` reference: Tencent Finance batch quotes first, then Sina batch quotes for missing or failed symbols. If neither source is usable, keep the latest official Tushare closing prices visible and label the fallback explicitly.
- Treat Tencent/Sina values as a display-only overlay. Never persist them into `close_prices`, never relabel them as official closes, and never let an intraday failure alter the ledger, cost basis, or clearance P&L.
- Recalculate displayed market value, unrealized P&L, return, weights, charts, and industry totals from the overlay in memory. Retain `price_source`, `quote_time`, coverage, missing symbols, provider errors, and the 60-second interval in dashboard metadata.
- Cache a successful server response for slightly less than one refresh interval so multiple local tabs do not multiply upstream requests. Pause browser polling while the page is hidden and refresh once when it becomes visible again.
- Do not high-frequency poll Eastmoney for this feature. The reviewed upstream reference prioritizes Tencent/mootdx for quotes and warns that Eastmoney endpoints share IP-level rate controls.

Industry perspective is also private bookkeeping output. Use Tushare `stock_basic.industry` as the raw label for A-share equities, then normalize it without overwriting the source label. Classify an ETF from its latest usable disclosed constituent set and constituent industry distribution according to `references/etf_industry_classification.md`; for cross-market constituents, use the documented structured-industry and same-date-close fallback chain before declaring a coverage gap. Treat the ETF name as corroboration or an explicitly labeled low-confidence fallback. A tracking-index name may select a reviewed, machine-readable theme aggregation only after constituent coverage passes and the aggregated constituent weight meets its own threshold; it may never create the result alone. Preserve `未分类（ETF持仓覆盖不足）` when constituent coverage, freshness, or weighting is inadequate. Always retain source dates and methods, and never write these portfolio classifications into segment-company mapping or research evidence artifacts.

Clearance P&L is derived by replaying the private ledger; do not persist a second manually editable profit table. One cycle starts when quantity moves from zero to positive (or from the opening snapshot) and closes only when quantity returns to zero. Include moving-average released cost, sell fees, and cash income/fees recorded while that cycle is open. Keep realized P&L from still-open partial sales visible outside the completed-clearance total.

For Windows desktop launch, use `scripts/start_portfolio_dashboard.ps1`. It must reuse a healthy existing server, start a missing server with a hidden window, and open only the loopback dashboard URL in the user's default browser.

## Completion checks

- Affected quantities, total costs, market values, and P&L match the supplied evidence.
- Reconciled internal transfers match on security and quantity and have no ledger, cost-basis, or P&L effect.
- Pre-baseline statement details are classified from explicit inclusion evidence, not merely their dates; omitted trades are replayed and included trades are auditable without double counting.
- Re-importing the same statement is idempotent.
- Current prices include their trade dates and sources.
- K-line reads are cache-only until explicit refresh; qfq bars cite both raw-bar and factor sources, and every marker resolves to original ledger entries or an explicit coverage gap.
- Single-day minute reads are cache-only until explicit refresh or a dashboard-triggered refresh for the selected ledger BUY/SELL date; source, 1/5-minute precision, fallback reason, refresh time, mapped trades, and unlocated trades remain visible, and forced dual-source failure preserves the existing cache.
- Latest-view intraday prices include quote timestamps and provider coverage; forced provider failure falls back to stored closing prices without changing SQLite.
- Industry groups include raw and normalized classification sources. ETF labels are backed by dated constituent coverage and weighting metadata; broad, stale, insufficiently covered, or ambiguous ETFs remain visibly unclassified instead of falling back silently to their names.
- Completed clearance cycles reconcile to ledger realized P&L, and partial sales are not mislabeled as closed positions.
- Personal data is ignored by Git.
- Research workflow files are unchanged.
