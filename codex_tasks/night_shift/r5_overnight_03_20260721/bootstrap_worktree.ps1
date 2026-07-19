[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)]
  [string]$RepoRoot,

  [Parameter(Mandatory=$true)]
  [string]$WorktreeRoot,

  [string]$SourceBranch = "codex/r5-night02-contract-recovery",
  [string]$TargetBranch = "codex/r5-night03-targeted-backflow-intake",
  [switch]$Resume
)

$ErrorActionPreference = "Stop"
$ExpectedSourceCommit = "069da527452def6c59c3772750e933d8611ccadf"
$PackageFolderName = "r5_overnight_03_20260721"
$RepoPackageRelative = "codex_tasks/night_shift/r5_overnight_03_20260721"

function Invoke-Git {
  param([string[]]$Arguments, [string]$WorkingDirectory)
  $output = & git -C $WorkingDirectory @Arguments 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "git command failed: git -C `"$WorkingDirectory`" $($Arguments -join ' ')`n$output"
  }
  return ($output | Out-String).Trim()
}

$RepoRoot = (Resolve-Path $RepoRoot).Path
$PackageRoot = $PSScriptRoot

python (Join-Path $PackageRoot "tools\verify_package.py") $PackageRoot
if ($LASTEXITCODE -ne 0) {
  throw "Package validation failed."
}

Invoke-Git -Arguments @("fetch", "origin", "--prune") -WorkingDirectory $RepoRoot | Out-Null
$remoteLine = Invoke-Git -Arguments @("ls-remote", "--heads", "origin", $SourceBranch) -WorkingDirectory $RepoRoot
if (-not $remoteLine) {
  throw "Remote source branch not found: $SourceBranch"
}
$remoteSha = ($remoteLine -split "\s+")[0]
if ($remoteSha -ne $ExpectedSourceCommit) {
  throw "Remote source SHA mismatch. Expected $ExpectedSourceCommit, got $remoteSha"
}

if ($Resume) {
  if (-not (Test-Path $WorktreeRoot)) {
    throw "Resume requested but worktree does not exist: $WorktreeRoot"
  }
  $branch = Invoke-Git -Arguments @("branch", "--show-current") -WorkingDirectory $WorktreeRoot
  if ($branch -ne $TargetBranch) {
    throw "Resume branch mismatch. Expected $TargetBranch, got $branch"
  }
  Write-Host "Resume worktree verified: $WorktreeRoot"
  exit 0
}

if (Test-Path $WorktreeRoot) {
  throw "Worktree path already exists: $WorktreeRoot"
}

$existingLocal = (& git -C $RepoRoot branch --list $TargetBranch | Out-String).Trim()
if ($existingLocal) {
  throw "Local target branch already exists: $TargetBranch. Use a new target or -Resume."
}
$existingRemote = (& git -C $RepoRoot ls-remote --heads origin $TargetBranch | Out-String).Trim()
if ($existingRemote) {
  throw "Remote target branch already exists: $TargetBranch. Use -Resume after creating its worktree."
}

Invoke-Git -Arguments @("worktree", "add", "-b", $TargetBranch, $WorktreeRoot, $ExpectedSourceCommit) -WorkingDirectory $RepoRoot | Out-Null

$destination = Join-Path $WorktreeRoot ($RepoPackageRelative -replace "/", "\")
New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
Copy-Item -Path $PackageRoot -Destination $destination -Recurse -Force

Invoke-Git -Arguments @("add", $RepoPackageRelative) -WorkingDirectory $WorktreeRoot | Out-Null
$env:GIT_AUTHOR_NAME = "R5 Night Shift Bootstrap"
$env:GIT_AUTHOR_EMAIL = "night-shift-bootstrap@local.invalid"
$env:GIT_COMMITTER_NAME = "R5 Night Shift Bootstrap"
$env:GIT_COMMITTER_EMAIL = "night-shift-bootstrap@local.invalid"
Invoke-Git -Arguments @("commit", "--no-gpg-sign", "-m", "chore(night03): seed reviewed-decision task package") -WorkingDirectory $WorktreeRoot | Out-Null

$seed = Invoke-Git -Arguments @("rev-parse", "HEAD") -WorkingDirectory $WorktreeRoot
$parent = Invoke-Git -Arguments @("rev-parse", "HEAD^") -WorkingDirectory $WorktreeRoot
if ($parent -ne $ExpectedSourceCommit) {
  throw "Seed commit parent mismatch: $parent"
}

$localDir = Join-Path $WorktreeRoot ".local\night_shift"
New-Item -ItemType Directory -Path $localDir -Force | Out-Null
@{
  source_branch = $SourceBranch
  source_commit = $ExpectedSourceCommit
  target_branch = $TargetBranch
  seed_commit = $seed
  worktree_root = $WorktreeRoot
  package_path = $RepoPackageRelative
} | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $localDir "night03_bootstrap.json") -Encoding UTF8

python (Join-Path $destination "tools\verify_package.py") $destination
if ($LASTEXITCODE -ne 0) {
  throw "Copied package validation failed."
}

$status = Invoke-Git -Arguments @("status", "--porcelain") -WorkingDirectory $WorktreeRoot
if ($status) {
  throw "Worktree is not clean after seed commit:`n$status"
}

Write-Host ""
Write-Host "Night03 worktree ready."
Write-Host "Worktree: $WorktreeRoot"
Write-Host "Branch:   $TargetBranch"
Write-Host "Source:   $ExpectedSourceCommit"
Write-Host "Seed:     $seed"
Write-Host "Prompt:   $destination\scheduled_task_prompt.txt"
