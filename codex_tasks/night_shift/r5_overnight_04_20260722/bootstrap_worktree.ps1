[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$RepoRoot,
  [Parameter(Mandatory=$true)][string]$WorktreeRoot,
  [string]$SourceBranch = "codex/r5-night03-targeted-backflow-intake",
  [string]$TargetBranch = "codex/r5-night04-review-acceleration-and-unlock",
  [switch]$Resume
)

$ErrorActionPreference = "Stop"
$ExpectedSourceCommit = "758ab7557d9de9eea42a5aeb5df95e3d68c26f0c"
$PackageFolderName = "r5_overnight_04_20260722"
$RepoPackageRelative = "codex_tasks/night_shift/r5_overnight_04_20260722"

function Invoke-Git {
  param([string[]]$Arguments, [string]$WorkingDirectory)
  $output = & git -C $WorkingDirectory @Arguments 2>&1
  if ($LASTEXITCODE -ne 0) { throw "git failed: $($Arguments -join ' ')`n$output" }
  return ($output | Out-String).Trim()
}

$RepoRoot = (Resolve-Path $RepoRoot).Path
$PackageRoot = $PSScriptRoot
python (Join-Path $PackageRoot "tools\verify_package.py") $PackageRoot
if ($LASTEXITCODE -ne 0) { throw "Package validation failed." }

Invoke-Git -Arguments @("fetch","origin","--prune") -WorkingDirectory $RepoRoot | Out-Null
$remoteLine = Invoke-Git -Arguments @("ls-remote","--heads","origin",$SourceBranch) -WorkingDirectory $RepoRoot
if (-not $remoteLine) { throw "Remote source branch not found: $SourceBranch" }
$remoteSha = ($remoteLine -split "\s+")[0]
if ($remoteSha -ne $ExpectedSourceCommit) { throw "Remote source SHA mismatch: $remoteSha" }

if (Test-Path $WorktreeRoot) {
  if (-not $Resume) { throw "Worktree exists. Use -Resume only for the intended Night04 worktree." }
} else {
  Invoke-Git -Arguments @("worktree","add","-b",$TargetBranch,$WorktreeRoot,$ExpectedSourceCommit) -WorkingDirectory $RepoRoot | Out-Null
}

$destination = Join-Path $WorktreeRoot $RepoPackageRelative
New-Item -ItemType Directory -Path (Split-Path $destination) -Force | Out-Null
if (Test-Path $destination) { Remove-Item $destination -Recurse -Force }
Copy-Item $PackageRoot $destination -Recurse -Force

Invoke-Git -Arguments @("add","--",$RepoPackageRelative) -WorkingDirectory $WorktreeRoot | Out-Null
$env:GIT_AUTHOR_NAME = "R5 Night Shift Bootstrap"
$env:GIT_AUTHOR_EMAIL = "night-shift-bootstrap@local.invalid"
$env:GIT_COMMITTER_NAME = "R5 Night Shift Bootstrap"
$env:GIT_COMMITTER_EMAIL = "night-shift-bootstrap@local.invalid"
Invoke-Git -Arguments @("commit","--no-gpg-sign","-m","chore(night04): seed review-acceleration task package") -WorkingDirectory $WorktreeRoot | Out-Null

$parent = Invoke-Git -Arguments @("rev-parse","HEAD^") -WorkingDirectory $WorktreeRoot
if ($parent -ne $ExpectedSourceCommit) { throw "Seed parent mismatch: $parent" }
python (Join-Path $destination "tools\verify_package.py") $destination
if ($LASTEXITCODE -ne 0) { throw "Copied package validation failed." }

$status = Invoke-Git -Arguments @("status","--porcelain") -WorkingDirectory $WorktreeRoot
if ($status) { throw "Worktree not clean after seed:`n$status" }

Write-Host "Night04 worktree ready: $WorktreeRoot"
Write-Host "Branch: $TargetBranch"
Write-Host "Source: $ExpectedSourceCommit"
Write-Host "Prompt: $destination\scheduled_task_prompt.txt"
