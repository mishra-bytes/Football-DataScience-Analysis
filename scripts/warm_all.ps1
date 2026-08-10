# Warm the FBref cache for all five leagues, strictly one at a time.
#
# Concurrency is deliberately absent. soccerdata drives seleniumbase in
# undetected mode, which spawns roughly 40 Chrome processes per session; three
# concurrent leagues took this machine from 15 GB free to 0.8 GB and slowed each
# fetch from ~30 s to ~250 s. One league at a time is both safer and faster.
#
# Chrome is killed between leagues because undetected-chromedriver reliably
# leaves orphans behind on Windows.

param(
    [string]$LogDir = $PSScriptRoot
)

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
$py = Join-Path $repo ".venv\Scripts\python.exe"
$leagues = @('ENG-Premier League', 'ESP-La Liga', 'ITA-Serie A', 'GER-Bundesliga', 'FRA-Ligue 1')

foreach ($league in $leagues) {
    $tag = ($league -split '-')[0]
    Write-Output "=== START $league $(Get-Date -Format 'HH:mm:ss') ==="
    & $py (Join-Path $repo "scripts\warm_cache.py") $league 2>&1 |
        Tee-Object -FilePath (Join-Path $LogDir "seq_$tag.log")

    Get-Process chrome, uc_driver, chromedriver -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 5
    Write-Output "=== END $league $(Get-Date -Format 'HH:mm:ss') ==="
}

Get-Process chrome, uc_driver, chromedriver -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Write-Output "=== ALL LEAGUES DONE $(Get-Date -Format 'HH:mm:ss') ==="
