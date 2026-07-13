[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".conda\investment-system\python.exe"
$dashboardUrl = "http://127.0.0.1:$Port/"
$healthUrl = "${dashboardUrl}health"

function Test-PortfolioDashboard {
    try {
        $response = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        return $response.status -eq "ok"
    }
    catch {
        return $false
    }
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

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    Show-LauncherError "未找到项目 Python 环境：`n$pythonPath"
    exit 1
}

if (-not (Test-PortfolioDashboard)) {
    $serverArguments = @(
        "-m",
        "src.portfolio",
        "web",
        "--no-open",
        "--host",
        "127.0.0.1",
        "--port",
        [string]$Port
    )

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

# 浏览器是用户需要直接操作的前台程序，因此保持正常可见。
Start-Process -FilePath $dashboardUrl
