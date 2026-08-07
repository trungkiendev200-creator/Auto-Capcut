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
$tag = "v1.27.0"
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
Canvas Blur (tab Create Project 2 -> Manhwa) gio chon duoc 4 muc mo:

- Them dropdown mask1 / mask2 / mask3 / mask4 canh checkbox Canvas Blur.
  mask1 mo nhe nhat -> mask4 mo nhat, dung theo thu tu 4 o Nen -> Mo trong CapCut.
- Dropdown tu xam khi checkbox Canvas Blur dang tat.
- Hop xac nhan hien ten mask dang chon thay vi chi ON/OFF.
- Mac dinh la mask1, trung dung muc mo cu -> ai dang dung khong thay khac gi.
"@

$payload = @{
    tag_name = $tag
    name = "v1.27.0 - Canvas Blur co 4 muc mask1-mask4"
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
