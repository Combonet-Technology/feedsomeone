param(
    [string]$Url = "http://127.0.0.1:8000/login/",
    [string]$OutputDirectory = (Join-Path $env:TEMP "feedsomeone-ui-verification")
)

$chromeCandidates = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
)
$chrome = $chromeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $chrome) {
    Write-Error "Chrome is required for UI verification."
    exit 1
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$profile = Join-Path $env:TEMP ("feedsomeone-ui-profile-" + [guid]::NewGuid().ToString())

$captures = @(
    @{ Name = "login-desktop.png"; Size = "1200,900" },
    @{ Name = "login-mobile.png"; Size = "390,844" }
)

foreach ($capture in $captures) {
    $screenshot = Join-Path $OutputDirectory $capture.Name
    $userData = $profile + "-" + $capture.Name
    & $chrome "--headless=new" "--disable-gpu" "--no-sandbox" "--hide-scrollbars" "--window-size=$($capture.Size)" "--user-data-dir=$userData" "--screenshot=$screenshot" $Url | Out-Null
    if (-not (Test-Path -LiteralPath $screenshot)) {
        Write-Error "Chrome did not create $screenshot"
        exit 1
    }
    Write-Output $screenshot
}
