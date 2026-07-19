param(
    [string]$RepoRoot = "C:\Projects\03_Investment_System",
    [string]$WorktreeRoot = "C:\Projects\03_Investment_System_night02",
    [string]$SourceBranch = "codex/r5-night01-autonomous-harness",
    [string]$TargetBranch = "codex/r5-night02-contract-recovery",
    [string]$SourceSha = "4340945457d661ed62967e949f862ccf2214aff2"
)

$ErrorActionPreference = "Stop"

function Invoke-Git([string]$Cwd, [string[]]$Arguments) {
    $output = & git -C $Cwd @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git -C '$Cwd' $($Arguments -join ' ') failed:`n$output"
    }
    return ($output | Out-String).Trim()
}

if (-not (Test-Path $RepoRoot)) { throw "RepoRoot does not exist: $RepoRoot" }
$gitMarker = Join-Path $RepoRoot ".git"
if (-not (Test-Path $gitMarker)) { throw "RepoRoot is not a Git checkout/worktree: $RepoRoot" }
if ($WorktreeRoot -match "codex/") { throw "WorktreeRoot contains a branch fragment; path and branch must be separate." }
if ($TargetBranch -match "^[A-Za-z]:\\") { throw "TargetBranch contains a Windows path; path and branch must be separate." }

Invoke-Git $RepoRoot @("fetch", "origin", $SourceBranch) | Out-Null
$remoteSha = Invoke-Git $RepoRoot @("rev-parse", "origin/$SourceBranch")
if ($remoteSha -ne $SourceSha) {
    throw "Source SHA mismatch. Expected $SourceSha, got $remoteSha"
}

if (Test-Path $WorktreeRoot) {
    $existingTop = Invoke-Git $WorktreeRoot @("rev-parse", "--show-toplevel")
    $existingBranch = Invoke-Git $WorktreeRoot @("branch", "--show-current")
    if ($existingBranch -ne $TargetBranch) {
        throw "Existing worktree uses '$existingBranch', expected '$TargetBranch'."
    }
} else {
    & git -C $RepoRoot show-ref --verify --quiet "refs/heads/$TargetBranch"
    if ($LASTEXITCODE -eq 0) {
        Invoke-Git $RepoRoot @("worktree", "add", $WorktreeRoot, $TargetBranch) | Out-Null
    } else {
        Invoke-Git $RepoRoot @("worktree", "add", "-b", $TargetBranch, $WorktreeRoot, $SourceSha) | Out-Null
    }
}

$head = Invoke-Git $WorktreeRoot @("rev-parse", "HEAD")
if ($head -ne $SourceSha) { throw "Night02 worktree did not start at exact source SHA: $head" }
$status = Invoke-Git $WorktreeRoot @("status", "--porcelain")
if ($status) { throw "Night02 worktree is not clean:`n$status" }

$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$destination = Join-Path $WorktreeRoot "codex_tasks\night_shift\r5_overnight_02_20260720"
New-Item -ItemType Directory -Force -Path $destination | Out-Null
Get-ChildItem -Path $packageRoot -Force | Where-Object { $_.Name -notin @("PACKAGE_MANIFEST.yaml", "PACKAGE_SHA256.txt") } | ForEach-Object {
    Copy-Item $_.FullName -Destination $destination -Recurse -Force
}

Write-Host "Night02 worktree ready: $WorktreeRoot"
Write-Host "Branch: $TargetBranch"
Write-Host "HEAD: $head"
Write-Host "Package copied to: $destination"
