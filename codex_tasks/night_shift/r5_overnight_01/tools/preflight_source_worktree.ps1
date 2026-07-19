param(
    [string]$SourceRoot = 'C:\Projects\03_Investment_System_bf2',
    [string]$ExpectedSha = '36a801efc2bf0af10ad9702b8c6266ebf1935d6f'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path $SourceRoot).Path
$head = (git -C $root rev-parse HEAD).Trim()
$status = git -C $root status --short

[ordered]@{
    source_root = $root
    expected_sha = $ExpectedSha
    actual_sha = $head
    sha_matches = ($head -eq $ExpectedSha)
    status = @($status)
    local_paths = [ordered]@{
        local = (Join-Path $root '.local')
        bf2_reports_glob = (Join-Path $root 'reports\p1_6\r5_bundle17r_bf2*')
    }
} | ConvertTo-Json -Depth 8

if ($head -ne $ExpectedSha) { exit 3 }
