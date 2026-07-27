[CmdletBinding()]
param(
    [ValidateRange(8766, 8770)]
    [int]$Port = 8766,
    [switch]$NoOpen
)

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
    throw "只读验收启动器只能从专用 worktree 运行: $expectedRepoRoot"
}

$pythonPath = "C:\Projects\03_Investment_System\.conda\investment-system\python.exe"
$portfolioDb = "C:\Projects\03_Investment_System\data\db\portfolio.sqlite3"
$candidateDb = Join-Path $repoRoot "data\db\investment_review_reviewability_v3.sqlite3"
$artifactRoot = Join-Path $repoRoot ".codex_tmp\investment_review_product_completion_v5\p7_real\runner_artifacts"
$expectedCandidateSha256 = "acf3b9c567cbe69ca4536285f4b5027016dd2e0ee2d382ebc4d993ff83410f38"
$runtimeRoot = Join-Path $repoRoot ".codex_tmp\investment_review_local_acceptance_readiness_v1\runtime"
$manifestPath = Join-Path $runtimeRoot "current.json"

foreach ($requiredFile in @($pythonPath, $portfolioDb, $candidateDb)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "缺少只读验收必需文件: $requiredFile"
    }
}
if (-not (Test-Path -LiteralPath $artifactRoot -PathType Container)) {
    throw "缺少已验收复盘产物目录: $artifactRoot"
}

$candidateSha256 = (
    Get-FileHash -Algorithm SHA256 -LiteralPath $candidateDb
).Hash.ToLowerInvariant()
if ($candidateSha256 -ne $expectedCandidateSha256) {
    throw "候选复盘库 SHA-256 不匹配，拒绝启动"
}
if (
    (Test-Path -LiteralPath "$candidateDb-wal") -or
    (Test-Path -LiteralPath "$candidateDb-shm")
) {
    throw "候选复盘库不是关闭态（WAL/SHM 应不存在），拒绝启动"
}

$listeners = @(
    Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
)
if ($listeners.Count -gt 0) {
    $owners = ($listeners | Select-Object -ExpandProperty OwningProcess -Unique) -join ","
    throw "端口 $Port 已被 PID $owners 占用；启动器不会复用或终止未知进程"
}

New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssfffZ")
$stdoutPath = Join-Path $runtimeRoot "$stamp.stdout.log"
$stderrPath = Join-Path $runtimeRoot "$stamp.stderr.log"
$url = "http://127.0.0.1:$Port/"
$arguments = @(
    "-B",
    "-m",
    "src.portfolio",
    "--db",
    $portfolioDb,
    "web",
    "--host",
    "127.0.0.1",
    "--port",
    [string]$Port,
    "--no-open",
    "--no-review-automation",
    "--investment-review-acceptance",
    "--investment-review-db",
    $candidateDb,
    "--investment-review-artifact-root",
    $artifactRoot,
    "--investment-review-candidate-sha256",
    $expectedCandidateSha256
)

$previousBytecodeSetting = $env:PYTHONDONTWRITEBYTECODE
$env:PYTHONDONTWRITEBYTECODE = "1"
try {
    $process = Start-Process `
        -FilePath $pythonPath `
        -ArgumentList $arguments `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -PassThru
}
finally {
    if ($null -eq $previousBytecodeSetting) {
        Remove-Item Env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONDONTWRITEBYTECODE = $previousBytecodeSetting
    }
}

try {
    $health = $null
    for ($attempt = 0; $attempt -lt 80; $attempt += 1) {
        if ($process.HasExited) {
            throw "只读验收服务提前退出，exit=$($process.ExitCode)"
        }
        try {
            $health = Invoke-RestMethod `
                -Uri "${url}health" `
                -Method Get `
                -TimeoutSec 2
            break
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
    }
    if ($null -eq $health) {
        throw "只读验收服务在 20 秒内未通过健康检查"
    }
    if (
        $health.review_acceptance_read_only -ne $true -or
        $health.acceptance_task_id -ne $taskId -or
        $health.review_candidate_sha256 -ne $expectedCandidateSha256 -or
        $health.automation_enabled -ne $false -or
        $health.external_network_allowed -ne $false -or
        $health.human_product_acceptance -ne "pending" -or
        $health.production_released -ne $false
    ) {
        throw "端口健康身份与只读验收合同不匹配"
    }

    $head = (& git -C $repoRoot rev-parse HEAD).Trim()
    $manifest = [ordered]@{
        schema_version = "investment_review.local_acceptance_runtime.v1"
        task_id = $taskId
        started_at = [DateTime]::UtcNow.ToString("o")
        process_start_time = $process.StartTime.ToUniversalTime().ToString("o")
        pid = $process.Id
        executable = $pythonPath
        command_arguments = $arguments
        repo_root = $repoRoot
        git_head = $head
        host = "127.0.0.1"
        port = $Port
        url = $url
        portfolio_db = $portfolioDb
        review_db = $candidateDb
        review_candidate_sha256 = $expectedCandidateSha256
        artifact_root = $artifactRoot
        stdout_path = $stdoutPath
        stderr_path = $stderrPath
        health = $health
        stopped_at = $null
    }
    $manifest | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $manifestPath -Encoding utf8

    if (-not $NoOpen) {
        Start-Process $url | Out-Null
    }
    [ordered]@{
        status = "running"
        task_id = $taskId
        pid = $process.Id
        url = $url
        manifest = $manifestPath
        human_product_acceptance = "pending"
        production_released = $false
    } | ConvertTo-Json -Depth 4
}
catch {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
        Wait-Process -Id $process.Id -Timeout 10 -ErrorAction SilentlyContinue
    }
    throw
}
