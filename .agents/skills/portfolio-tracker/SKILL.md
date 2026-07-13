---
name: portfolio-tracker
description: Maintain the repo-local private portfolio ledger from holding screenshots, broker CSV/XLSX statements, Tushare closing prices, source-labeled industry classifications, and completed clearance-cycle P&L. Use for opening snapshots, statement reconciliation, cost/P&L refreshes, closed-position returns, industry perspective, and portfolio audits. This is a standalone utility skill and must never route through or mutate the research-orchestrator workflow.
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
   - on/before baseline and already reflected in the snapshot: record with `--included-in-opening`; never double count;
   - unclear: keep it un-applied and report the exact ambiguity.
6. Refresh latest available closing prices and industry classifications, render the CLI or local dashboard, and verify totals and affected securities. When the dashboard is on the latest view, also verify the non-persistent intraday quote overlay and its source/time labels.
7. When sell entries reduce a security to zero, verify the completed clearance cycle: released moving-average cost, net sale proceeds, cycle cash income/fees, realized P&L, and return percentage. Never label a still-open partial sale as a completed clearance.
8. Run `tests/test_portfolio_tracker.py` and `tests/test_portfolio_web.py`, then check that private files remain ignored.

## Holding screenshots

Before the opening snapshot has been imported, consolidate corrections in an ignored file such as `data/db/portfolio_opening_YYYY-MM-DD.csv`, then import once:

```powershell
.\.conda\investment-system\python.exe -m src.portfolio import-opening `
  --input data\db\portfolio_opening_YYYY-MM-DD.csv
```

Prefer exact `total_cost = market_value - unrealized_pnl` over a rounded displayed cost price. Retain the displayed cost price only as a cross-check.

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

For old statements already included in the opening snapshot, preview and apply with both `--included-in-opening` and `--apply`. Confirm afterward with `reconciliations`; these records must not change quantity or cost.

Reject or leave explicit TODOs for financing/margin trades, stock dividends, splits, transfers, and other events whose cost basis is not determined by the supplied evidence.

## Prices and verification

```powershell
.\.conda\investment-system\python.exe -m src.portfolio refresh-prices
.\.conda\investment-system\python.exe -m src.portfolio refresh-industries
.\.conda\investment-system\python.exe -m src.portfolio show
.\.conda\investment-system\python.exe -m src.portfolio closed
.\.conda\investment-system\python.exe -m src.portfolio web
.\.conda\investment-system\python.exe -m src.portfolio ledger
.\.conda\investment-system\python.exe -m src.portfolio reconciliations
```

Report the closing date actually returned by Tushare. Distinguish a successful core Tushare call from endpoint-specific permission failures. If any security is missing a price, do not present portfolio totals as complete.

The dashboard must stay loopback-only. It may read the same private ledger and invoke the existing price refresh command, but it must not add research-workflow routes, manifests, reports, or orchestration side effects.

### Intraday dashboard quotes

- The latest dashboard view refreshes intraday quotes every 60 seconds while the page is visible. Historical `as_of` views never use intraday quotes.
- Use the source order validated from the upstream `simonlin1212/a-stock-data` reference: Tencent Finance batch quotes first, then Sina batch quotes for missing or failed symbols. If neither source is usable, keep the latest official Tushare closing prices visible and label the fallback explicitly.
- Treat Tencent/Sina values as a display-only overlay. Never persist them into `close_prices`, never relabel them as official closes, and never let an intraday failure alter the ledger, cost basis, or clearance P&L.
- Recalculate displayed market value, unrealized P&L, return, weights, charts, and industry totals from the overlay in memory. Retain `price_source`, `quote_time`, coverage, missing symbols, provider errors, and the 60-second interval in dashboard metadata.
- Cache a successful server response for slightly less than one refresh interval so multiple local tabs do not multiply upstream requests. Pause browser polling while the page is hidden and refresh once when it becomes visible again.
- Do not high-frequency poll Eastmoney for this feature. The reviewed upstream reference prioritizes Tencent/mootdx for quotes and warns that Eastmoney endpoints share IP-level rate controls.

Industry perspective is also private bookkeeping output. Use Tushare `stock_basic.industry` for equities. Classify an ETF only when its instrument name contains an explicit industry theme; otherwise preserve `未分类（ETF）`. Always retain `industry_source` and never write these portfolio classifications into segment-company mapping or research evidence artifacts.

Clearance P&L is derived by replaying the private ledger; do not persist a second manually editable profit table. One cycle starts when quantity moves from zero to positive (or from the opening snapshot) and closes only when quantity returns to zero. Include moving-average released cost, sell fees, and cash income/fees recorded while that cycle is open. Keep realized P&L from still-open partial sales visible outside the completed-clearance total.

For Windows desktop launch, use `scripts/start_portfolio_dashboard.ps1`. It must reuse a healthy existing server, start a missing server with a hidden window, and open only the loopback dashboard URL in the user's default browser.

## Completion checks

- Affected quantities, total costs, market values, and P&L match the supplied evidence.
- Pre-baseline statement details are auditable but not double counted.
- Re-importing the same statement is idempotent.
- Current prices include their trade dates and sources.
- Latest-view intraday prices include quote timestamps and provider coverage; forced provider failure falls back to stored closing prices without changing SQLite.
- Industry groups include classification sources; thematic ETFs are classified when explicit, while broad or ambiguous ETFs remain visible as unclassified.
- Completed clearance cycles reconcile to ledger realized P&L, and partial sales are not mislabeled as closed positions.
- Personal data is ignored by Git.
- Research workflow files are unchanged.
