param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$NightShiftArgs
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$entrypoint = Join-Path $repoRoot 'scripts\run_r5_night_shift.py'
& python $entrypoint @NightShiftArgs
exit $LASTEXITCODE
