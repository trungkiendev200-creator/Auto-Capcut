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
$tag = "v1.26.0"
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
Auto Stories gio dung project giong het mau "brazil stories01":

- Hieu ung "Khung phim 1" ap len MOI segment video (ca video stock nen lan anh).
- Anh overlay: zoom con 85%, nam o track overlay, co mask "Cuon phim"
  (Lam mo vien 100). Mask luu theo ti le nen tu bam full chieu cao tung anh.
- Them sticker Subscribe o goc duoi-phai, dai bang ca project.
- Them 3 checkbox trong tab Auto Stories de bat/tat tung phan (mac dinh bat het).
- Bo han chuc nang import caption tu file .srt.
"@

$payload = @{
    tag_name = $tag
    name = "v1.26.0 - Auto Stories dung theo mau brazil stories01"
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
