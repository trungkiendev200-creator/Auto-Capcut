param(
    [string]$Repo = "trungkiendev200-creator/Auto-Capcut",
    [string]$Token = ""
)

# Auto-create GitHub Release with AutoCapCut.exe
$ErrorActionPreference = "Stop"

if ($Token) {
    # Use explicitly provided token (e.g. PAT for a different account)
    $token = $Token
    Write-Host "Using provided token (length=$($token.Length))"
} else {
    # Extract token from Git Credential Manager.
    # PowerShell pipeline to native exes loses LF/CR info; write a temp file
    # and shell-redirect instead.
    $tmpFile = [IO.Path]::GetTempFileName()
    [IO.File]::WriteAllBytes($tmpFile,
        [Text.Encoding]::ASCII.GetBytes("protocol=https`nhost=github.com`n`n"))
    $cred = & cmd /c "git credential fill < `"$tmpFile`""
    Remove-Item $tmpFile -Force

    $token = $null
    foreach ($line in $cred) {
        if ($line -match '^password=(.+)$') { $token = $Matches[1]; break }
    }
    if (-not $token) { throw "Could not extract GitHub token from credential manager" }
    Write-Host "Token extracted from credential manager (length=$($token.Length))"
}

$repo = $Repo
$tag = "v1.20.0"
$exePath = "dist\AutoCapCut.exe"

if (-not (Test-Path $exePath)) { throw "Missing $exePath" }

$headers = @{
    Authorization = "Bearer $token"
    Accept = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
    "User-Agent" = "AutoCapCut-Release"
}

$bodyText = @"
## Cap nhat
- Them chuc nang Split Picture (trong tab Sync Audio): cat moi anh dai hon a giay
  thanh nhieu doan ngan (ngau nhien trong [x;y]), giup them hieu ung cho do chan.
- Tuy chon Mirror: lat ngang xen ke ~50% cac doan cat ra.
- Sua loi 'khoang chet': anh dai luon duoc cat ke ca khi y < 2x.
- Create Project: bao popup ro khi batch tao 0 project (sai ten thu muc con).
"@

$payload = @{
    tag_name = $tag
    name = "v1.20.0 - Split Picture"
    body = $bodyText
    draft = $false
    prerelease = $false
} | ConvertTo-Json -Depth 5

Write-Host "Creating release..."
$release = Invoke-RestMethod `
    -Uri "https://api.github.com/repos/$repo/releases" `
    -Method Post -Headers $headers -Body $payload `
    -ContentType "application/json; charset=utf-8"

Write-Host "Release created: $($release.html_url)"
Write-Host "Uploading asset..."

# upload_url is templated: https://uploads.github.com/...{?name,label}
$uploadBase = $release.upload_url -replace '\{\?name,label\}',''
$uploadUrl = "$uploadBase`?name=AutoCapCut.exe"

$asset = Invoke-RestMethod `
    -Uri $uploadUrl -Method Post -Headers $headers `
    -InFile $exePath -ContentType "application/octet-stream"

Write-Host "Asset uploaded: $($asset.browser_download_url)"
Write-Host ""
Write-Host "DONE: $($release.html_url)"
