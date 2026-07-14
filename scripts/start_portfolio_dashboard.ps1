[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeCandidates = @($projectRoot)

# Linked worktrees keep code isolated, while the private runtime and ledger stay
# in the primary worktree. In a normal checkout both roots resolve identically.
$gitPointerPath = Join-Path $projectRoot ".git"
if (Test-Path -LiteralPath $gitPointerPath -PathType Leaf) {
    $gitPointer = Get-Content -LiteralPath $gitPointerPath -TotalCount 1
    if ($gitPointer -match "^gitdir:\s*(.+)$") {
        $linkedGitDir = $Matches[1].Trim()
        if (-not [IO.Path]::IsPathRooted($linkedGitDir)) {
            $linkedGitDir = Join-Path $projectRoot $linkedGitDir
        }
        $worktreesDir = Split-Path -Parent $linkedGitDir
        $commonGitDir = Split-Path -Parent $worktreesDir
        $runtimeCandidates += Split-Path -Parent $commonGitDir
    }
}

# Keep Git discovery as a fallback for nonstandard worktree layouts, but do not
# require Git to be present in the environment inherited by a desktop shortcut.
try {
    $gitCommonDir = (& git -C $projectRoot rev-parse --path-format=absolute --git-common-dir 2>$null | Select-Object -First 1)
    if ($LASTEXITCODE -eq 0 -and $gitCommonDir) {
        $runtimeCandidates += Split-Path -Parent $gitCommonDir.Trim()
    }
}
catch {
    # The .git pointer above is sufficient for a normal linked worktree.
}

$runtimeRoot = $runtimeCandidates |
    Select-Object -Unique |
    Where-Object {
        Test-Path -LiteralPath (Join-Path $_ ".conda\investment-system\python.exe") -PathType Leaf
    } |
    Select-Object -First 1

if (-not $runtimeRoot) {
    $runtimeRoot = $projectRoot
}

$pythonPath = Join-Path $runtimeRoot ".conda\investment-system\python.exe"
$databasePath = Join-Path $runtimeRoot "data\db\portfolio.sqlite3"
$envFilePath = Join-Path $runtimeRoot ".env.local"
$dashboardUrl = "http://127.0.0.1:$Port/"
$healthUrl = "${dashboardUrl}health"
$requiredApiVersion = 2
$requiredCapability = "refresh-intraday"

function Test-PortfolioDashboard {
    try {
        $response = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        return (
            $response.status -eq "ok" -and
            [int]$response.api_version -ge $requiredApiVersion -and
            @($response.capabilities) -contains $requiredCapability
        )
    }
    catch {
        return $false
    }
}

function Stop-IncompatiblePortfolioDashboard {
    $listeners = @(
        Get-NetTCPConnection `
            -LocalPort $Port `
            -State Listen `
            -ErrorAction SilentlyContinue
    )
    if (-not $listeners) {
        return
    }

    $listenerProcessIds = @($listeners.OwningProcess | Select-Object -Unique)
    $listenerProcesses = @(
        Get-CimInstance Win32_Process |
            Where-Object { $_.ProcessId -in $listenerProcessIds }
    )
    $expectedPython = [IO.Path]::GetFullPath($pythonPath)
    $databasePattern = [regex]::Escape([IO.Path]::GetFullPath($databasePath))
    $portPattern = "--port\s+$Port(?:\s|$)"

    foreach ($process in $listenerProcesses) {
        $executable = if ($process.ExecutablePath) {
            [IO.Path]::GetFullPath($process.ExecutablePath)
        }
        else {
            ""
        }
        $commandLine = [string]$process.CommandLine
        $isOwnedPortfolioServer = (
            $executable.Equals($expectedPython, [StringComparison]::OrdinalIgnoreCase) -and
            $commandLine -match "-m\s+src\.portfolio(?:\s|$)" -and
            $commandLine -match $portPattern -and
            $commandLine -match $databasePattern
        )
        if (-not $isOwnedPortfolioServer) {
            throw "端口 $Port 被其他程序占用，未自动终止进程 $($process.ProcessId)。"
        }
    }

    foreach ($process in $listenerProcesses) {
        Stop-Process -Id $process.ProcessId -ErrorAction Stop
    }
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 100
        $remaining = Get-NetTCPConnection `
            -LocalPort $Port `
            -State Listen `
            -ErrorAction SilentlyContinue
        if (-not $remaining) {
            return
        }
    }
    throw "旧版持仓服务未能释放端口 $Port。"
}

function Show-LauncherError {
    param([Parameter(Mandatory = $true)][string]$Message)

    try {
        $shell = New-Object -ComObject WScript.Shell
        [void]$shell.Popup($Message, 0, "持仓账本启动失败", 16)
    }
    catch {
        Write-Error $Message
    }
}

function Open-PortfolioDashboard {
    param([Parameter(Mandatory = $true)][string]$Url)

    $edgeCandidates = @(
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "$env:LocalAppData\Microsoft\Edge\Application\msedge.exe"
    )
    $edgePath = $edgeCandidates |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1

    try {
        if ($edgePath) {
            Start-Process `
                -FilePath $edgePath `
                -ArgumentList @("--new-window", "--app=$Url", "--start-maximized") `
                -WindowStyle Normal | Out-Null
        }
        else {
            # Explorer invokes the registered HTTP handler more reliably than
            # passing a URL directly to Start-Process on some Windows setups.
            Start-Process `
                -FilePath "explorer.exe" `
                -ArgumentList @($Url) `
                -WindowStyle Normal | Out-Null
        }
        return $true
    }
    catch {
        Show-LauncherError "持仓服务已启动，但无法打开页面：`n$Url`n`n$($_.Exception.Message)"
        return $false
    }
}

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    Show-LauncherError "未找到项目 Python 环境：`n$pythonPath"
    exit 1
}

if (-not (Test-PortfolioDashboard)) {
    try {
        Stop-IncompatiblePortfolioDashboard
    }
    catch {
        Show-LauncherError $_.Exception.Message
        exit 1
    }

    $serverArguments = @(
        "-m",
        "src.portfolio",
        "--db",
        $databasePath,
        "web",
        "--no-open",
        "--host",
        "127.0.0.1",
        "--port",
        [string]$Port
    )

    if (Test-Path -LiteralPath $envFilePath -PathType Leaf) {
        $serverArguments += @("--env-file", $envFilePath)
    }

    Start-Process `
        -FilePath $pythonPath `
        -ArgumentList $serverArguments `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden | Out-Null

    $started = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 250
        if (Test-PortfolioDashboard) {
            $started = $true
            break
        }
    }

    if (-not $started) {
        Show-LauncherError "本地服务未能在 10 秒内启动。请检查端口 $Port 是否被其他程序占用。"
        exit 1
    }
}

# 页面以可见的独立应用窗口打开；失败时必须向用户显示原因。
if (-not (Open-PortfolioDashboard -Url $dashboardUrl)) {
    exit 1
}
