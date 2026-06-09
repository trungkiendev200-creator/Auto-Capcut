param(
    [string]$Repo = "trungkiendev200-creator/Auto-Capcut"
)

# Auto-create GitHub Release with AutoCapCut.exe
$ErrorActionPreference = "Stop"

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
Write-Host "Token extracted (length=$($token.Length))"

$repo = $Repo
$tag = "v1.19.0"
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
- Doi label footer thanh Auto-Capcut.
- Ban chuyen tiep: tu phien ban nay app se tu dong cap nhat tu repo moi.
"@

$payload = @{
    tag_name = $tag
    name = "v1.19.0 - Auto-Capcut"
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
