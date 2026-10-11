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
$tag = "v1.29.0"
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

### BDC (tab BODYCAM) - 4 chuc nang moi
- **Change Video**: xoa track sub + track anh, thay narration mp3 va video
  nen chay tren no bang video dung san trong thu muc video-narration/.
- **Chen Intro/Outro**: chen video intro/outro khop ten voi project
  (intro-videoNNN.mp4 / outro-videoNNN.mp4), tu dong dich timeline.
- **clear-sub-blur**: xoa sub va cat effect Blur quanh cac doan
  narration/outro/intro. Nhan Blur theo resource_id thay vi ten hien thi,
  nen hoat dong dung du CapCut dang de ngon ngu nao (vd 'Mo' tieng Viet).
- **Effect narration**: random 1 effect mau (lay tu project 'effect
  narration') cho moi doan narration/intro.

### Tab Template (trong Caption)
Luu va ap style caption (font, mau, effect, animation, vi tri) giua cac
project, giu nguyen noi dung/timing tung caption. Ho tro ca caption thuong
lan caption da ap Text Template co san cua CapCut.

### Sua loi
- parse_delete_input gio nhan ca dinh dang nhieu range cach nhau bang dau
  phay tren 1 dong (dung format da ghi trong UI tu truoc), truoc day chi
  nhan duoc moi dong 1 range nen hay bao loi sai khi file duoc gop dong.

### Don dep giao dien
- Bo man hinh mat khau VIP5AE, doi ten tab thanh BODYCAM.
- Gop tab Chen Intro va Chen Outro lam 1 cho gon.
- Bo cac chuc nang khong con dung: Cut & Import, Xoa SRT, Sync Media, Insert
  Picture, PROMAX (trong BODYCAM); Split Picture, Ani-Trans-Story, Key Frame
  Nang Cao (trong Sync Audio); Split projects, Split project 2 (trong Create
  Project 2).
"@

$payload = @{
    tag_name = $tag
    name = "v1.29.0 - Change Video, Chen Intro/Outro, Template chu, Effect narration"
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
