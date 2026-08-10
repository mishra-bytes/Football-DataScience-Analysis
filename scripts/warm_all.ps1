# Warm the FBref cache for all five leagues, strictly one at a time.
#
# Concurrency is deliberately absent. soccerdata drives seleniumbase in
# undetected mode, which spawns roughly 40 Chrome processes per session; three
# concurrent leagues took this machine from 15 GB free to 0.8 GB and slowed each
# fetch from ~30 s to ~250 s. One league at a time is both safer and faster.
#
# Chrome is NOT killed between leagues here: when two lanes run concurrently, a
# global Stop-Process would take down the other lane's live browser session.
# undetected-chromedriver leaves orphans on Windows, so the caller must clean up
# once every lane has finished.

# Leagues arrive as one semicolon-delimited string, not an array. League names
# contain spaces, and PowerShell's Start-Process -ArgumentList re-splits array
# elements on whitespace, which silently turns "ENG-Premier League" into two
# bogus arguments.
param(
    [string]$LogDir = $PSScriptRoot,
    [string]$LeagueList = 'ENG-Premier League;ESP-La Liga;ITA-Serie A;GER-Bundesliga;FRA-Ligue 1',
    [string]$Tag = "seq",
    # Comma-separated stat tables. `misc` is omitted by default: it only refines
    # the discipline requirement and can be backfilled later without a re-run.
    [string]$Stats = "standard,shooting,playing_time,keeper"
)

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
$py = Join-Path $repo ".venv\Scripts\python.exe"
$leagues = $LeagueList -split ';' | Where-Object { $_.Trim() -ne '' }

foreach ($league in $leagues) {
    $tag = ($league -split '-')[0]
    Write-Output "=== START $league $(Get-Date -Format 'HH:mm:ss') ==="
    & $py (Join-Path $repo "scripts\warm_cache.py") $league $Stats 2>&1 |
        Tee-Object -FilePath (Join-Path $LogDir "$Tag`_$tag.log")

    Write-Output "=== END $league $(Get-Date -Format 'HH:mm:ss') ==="
}

Write-Output "=== LANE $Tag DONE $(Get-Date -Format 'HH:mm:ss') ==="
