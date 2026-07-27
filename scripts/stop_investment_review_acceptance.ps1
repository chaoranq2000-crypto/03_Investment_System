[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$taskId = "investment_review_local_acceptance_readiness_v1"
$expectedRepoRoot = "C:\Projects\03_Investment_System_investment_review_reviewability"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
if (-not [string]::Equals(
    $repoRoot,
    $expectedRepoRoot,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "只读验收停止器只能从专用 worktree 运行: $expectedRepoRoot"
}

$manifestPath = Join-Path $repoRoot ".codex_tmp\investment_review_local_acceptance_readiness_v1\runtime\current.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "没有找到本任务的运行身份记录；不会猜测或终止进程"
}
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
if (
    $manifest.schema_version -ne "investment_review.local_acceptance_runtime.v1" -or
    $manifest.task_id -ne $taskId -or
    -not [string]::Equals(
        [string]$manifest.repo_root,
        $repoRoot,
        [System.StringComparison]::OrdinalIgnoreCase
    ) -or
    [string]$manifest.host -ne "127.0.0.1" -or
    [int]$manifest.port -lt 8766 -or
    [int]$manifest.port -gt 8770
) {
    throw "运行身份记录不属于本任务；不会终止进程"
}

$processId = [int]$manifest.pid
$process = Get-Process -Id $processId -ErrorAction SilentlyContinue
if ($null -eq $process) {
    if ($null -eq $manifest.stopped_at) {
        $manifest.stopped_at = [DateTime]::UtcNow.ToString("o")
    }
    $manifest |
        Add-Member `
            -NotePropertyName stop_status `
            -NotePropertyValue "already_stopped" `
            -Force
    $manifest | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $manifestPath -Encoding utf8
    [ordered]@{
        status = "already_stopped"
        task_id = $taskId
        pid = $processId
        manifest = $manifestPath
    } | ConvertTo-Json
    exit 0
}

$actualExecutable = $process.Path
$actualStartTime = $process.StartTime.ToUniversalTime()
try {
    $manifestStartTime = if ($manifest.process_start_time -is [DateTime]) {
        ([DateTime]$manifest.process_start_time).ToUniversalTime()
    }
    else {
        (
            [DateTimeOffset]::Parse(
                [string]$manifest.process_start_time,
                [System.Globalization.CultureInfo]::InvariantCulture
            )
        ).UtcDateTime
    }
}
catch {
    throw "运行身份记录中的启动时间无效；不会终止进程"
}
if (
    -not [string]::Equals(
        $actualExecutable,
        [string]$manifest.executable,
        [System.StringComparison]::OrdinalIgnoreCase
    ) -or
    $actualStartTime.Ticks -ne $manifestStartTime.Ticks
) {
    throw "PID 已被复用或可执行文件身份不匹配；不会终止进程"
}

$cim = Get-CimInstance Win32_Process -Filter "ProcessId = $processId"
$commandLine = [string]$cim.CommandLine
if (
    [string]::IsNullOrWhiteSpace($commandLine) -or
    -not $commandLine.Contains("--investment-review-acceptance") -or
    -not $commandLine.Contains([string]$manifest.review_db) -or
    -not $commandLine.Contains([string]$manifest.review_candidate_sha256)
) {
    throw "进程命令行未通过本任务只读验收身份校验；不会终止进程"
}

$healthUri = "http://127.0.0.1:$([int]$manifest.port)/health"
try {
    $health = Invoke-RestMethod -Uri $healthUri -Method Get -TimeoutSec 2
}
catch {
    $health = $null
}
if (
    $null -ne $health -and (
        $health.review_acceptance_read_only -ne $true -or
        $health.acceptance_task_id -ne $taskId -or
        $health.review_candidate_sha256 -ne [string]$manifest.review_candidate_sha256
    )
) {
    throw "端口健康身份不匹配；不会终止进程"
}

Stop-Process -Id $processId -Force
Wait-Process -Id $processId -Timeout 15 -ErrorAction SilentlyContinue
if ($null -ne (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
    throw "任务进程在 15 秒内未退出"
}
Start-Sleep -Milliseconds 250
$remaining = @(
    Get-NetTCPConnection `
        -State Listen `
        -LocalPort ([int]$manifest.port) `
        -ErrorAction SilentlyContinue |
        Where-Object { $_.OwningProcess -eq $processId }
)
if ($remaining.Count -gt 0) {
    throw "任务进程已退出，但原 PID 仍显示监听端口"
}

$manifest.stopped_at = [DateTime]::UtcNow.ToString("o")
$manifest |
    Add-Member `
        -NotePropertyName stop_status `
        -NotePropertyValue "stopped" `
        -Force
$manifest | ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath $manifestPath -Encoding utf8

[ordered]@{
    status = "stopped"
    task_id = $taskId
    pid = $processId
    port = [int]$manifest.port
    manifest = $manifestPath
} | ConvertTo-Json
