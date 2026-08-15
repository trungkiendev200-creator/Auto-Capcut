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
$tag = "v1.28.0"
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

### Them tab BDC (trong VIP5AE)
Chay 4 buoc giong 17 PROMAX, khac duy nhat cach map anh law:
- KHONG can file 3-insert-law-picture.txt nua.
- Anh dat ten bang so = so narration: 03.png -> audio 3, 20.png -> audio 20.
- Bo qua anh ten khong phai so, canh bao khi 2 anh trung so audio.

### On dinh hon cho 17 PROMAX
- Buoc Xoa SRT: go lo so o cuoi dai (vd 584-592 khi chi co 591 sub) gio chi
  BO QUA so thua kem canh bao, thay vi bao loi va bo ca project.
- Them preflight: kiem tra input ca 4 buoc TRUOC khi ghi. Sai thi bo qua
  project va KHONG dung vao draft, tranh tinh trang lam do dang (da cat va
  chen audio nhung chua xong cac buoc sau) roi chay lai bi cat chong.

### Don dep
- Bo tab Import Data.
- Bo tab Handle track image.
"@

$payload = @{
    tag_name = $tag
    name = "v1.28.0 - Them BDC, bo tab Import Data va Handle track image"
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
