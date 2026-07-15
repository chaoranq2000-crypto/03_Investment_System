param(
    [string]$Command = "status",
    [string]$Database = "data/db/investment_review.sqlite3",
    [string]$Python = ".\.conda\investment-system\python.exe",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Python)) {
    # Linked worktrees share the primary checkout's project environment. Keep
    # the default local path for normal checkouts, then resolve the primary
    # worktree before falling back to the active conda/PATH Python.
    $WorktreeLines = git worktree list --porcelain 2>$null
    if ($LASTEXITCODE -eq 0) {
        $PrimaryLine = $WorktreeLines | Where-Object { $_ -like "worktree *" } | Select-Object -First 1
        if ($PrimaryLine) {
            $PrimaryRoot = $PrimaryLine.Substring("worktree ".Length)
            $PrimaryPython = Join-Path $PrimaryRoot ".conda\investment-system\python.exe"
            if (Test-Path -LiteralPath $PrimaryPython) {
                $Python = $PrimaryPython
            }
        }
    }
}

if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

& $Python -m src.investment_review --db $Database $Command @RemainingArgs
exit $LASTEXITCODE
