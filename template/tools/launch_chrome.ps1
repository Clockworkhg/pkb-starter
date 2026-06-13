# launch_chrome.ps1 — Smart Chrome Debug Mode Launcher for PKB
#
# Usage:
#   powershell tools/launch_chrome.ps1           # Interactive (default)
#   powershell tools/launch_chrome.ps1 -Silent   # No confirmation prompts
#   powershell tools/launch_chrome.ps1 -Check    # Status only, don't launch
#
# What it does:
#   1. Detects Chrome installation
#   2. Checks if Chrome is already running with --remote-debugging-port=9222
#      by actually querying the debug endpoint (not just process check)
#   3. If not: launches Chrome with PKB-specific profile in .pkb-local/
#   4. Verifies the debug endpoint is reachable
#
# Profile location: .pkb-local/chrome-profile/
#   - Isolated from user's daily Chrome
#   - Preserves CNKI login state across sessions
#   - Never committed to Git (.gitignore)

param(
    [switch]$Silent,
    [switch]$Check
)

$DebugPort = if ($env:CHROME_DEBUG_PORT) { [int]$env:CHROME_DEBUG_PORT } else { 9222 }
$DebugHost = if ($env:CHROME_DEBUG_HOST) { $env:CHROME_DEBUG_HOST } else { "127.0.0.1" }
$DebugUrl = "http://${DebugHost}:${DebugPort}"

# PKB-specific profile (in .pkb-local/)
$PKB_ROOT = if ($env:PKB_ROOT) { $env:PKB_ROOT } else { Split-Path -Parent $MyInvocation.ScriptName }
$PKB_LOCAL = Join-Path $PKB_ROOT ".pkb-local"
$DebugUserData = Join-Path $PKB_LOCAL "chrome-profile"

# ── Find Chrome ──────────────────────────────────────────────────
$ChromePaths = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)

$ChromeExe = $null
foreach ($p in $ChromePaths) {
    if (Test-Path $p) { $ChromeExe = $p; break }
}

if (-not $ChromeExe) {
    $ChromeExe = (Get-Command "chrome.exe" -ErrorAction SilentlyContinue).Source
}
if (-not $ChromeExe) {
    $ChromeExe = (Get-Command "chrome" -ErrorAction SilentlyContinue).Source
}

if (-not $ChromeExe) {
    Write-Host "❌ Chrome not found. Please install Google Chrome."
    Write-Host "   Download: https://www.google.com/chrome/"
    exit 1
}

Write-Host "🔍 Chrome found: $ChromeExe"

# ── Ensure profile directory exists ─────────────────────────────
if (-not (Test-Path $DebugUserData)) {
    New-Item -ItemType Directory -Path $DebugUserData -Force | Out-Null
    Write-Host "📁 Created profile: $DebugUserData"
}

# ── Check if PKB debug instance is already running ──────────────
$AlreadyRunning = $false
$IsTargetInstance = $false
try {
    $response = Invoke-WebRequest -Uri "$DebugUrl/json" -TimeoutSec 3 -UseBasicParsing
    $pages = $response.Content | ConvertFrom-Json
    if ($pages -is [array] -and $pages.Count -gt 0) {
        $AlreadyRunning = $true
        $IsTargetInstance = $true
        Write-Host "✅ Chrome debug instance active ($($pages.Count) pages open)"
    }
} catch {
    Write-Host "  Chrome debug port ($DebugUrl) not active."
}

# Also check if debug port is open but not serving valid JSON
if (-not $AlreadyRunning) {
    try {
        $response = Invoke-WebRequest -Uri "$DebugUrl/json/version" -TimeoutSec 3 -UseBasicParsing
        $versionInfo = $response.Content | ConvertFrom-Json
        if ($versionInfo.Browser) {
            Write-Host "⚠️  Port $DebugPort is open by: $($versionInfo.Browser)"
            Write-Host "   This may be a non-PKB Chrome instance."
            $AlreadyRunning = $true
            $IsTargetInstance = $true
        }
    } catch {
        # Port not open or not Chrome debug
    }
}

# ── Check if other Chrome is running (without debug port) ───────
if (-not $AlreadyRunning) {
    try {
        $chromeProcesses = Get-Process "chrome" -ErrorAction SilentlyContinue
        if ($chromeProcesses) {
            Write-Host "⚠️  Chrome is running ($($chromeProcesses.Count) process(es)) but debug port $DebugPort is not reachable."
            Write-Host "   The running Chrome was NOT started with --remote-debugging-port=$DebugPort."
            Write-Host "   PKB will start its own Chrome instance with a separate profile."
        }
    } catch {
        # No Chrome running at all
    }
}

# ── Check mode ──────────────────────────────────────────────────
if ($Check) {
    if ($AlreadyRunning -and $IsTargetInstance) {
        Write-Host "✅ READY — CNKI skills can be used."
        Write-Host "   Profile: $DebugUserData"
        exit 0
    } elseif ($AlreadyRunning) {
        Write-Host "⚠️  Port $DebugPort is in use but may not be a PKB Chrome instance."
        Write-Host "   Verify: $DebugUrl/json"
        exit 1
    } else {
        Write-Host "❌ NOT READY — Chrome debug port $DebugPort not active."
        Write-Host "   Run without -Check to auto-launch."
        exit 1
    }
}

if ($AlreadyRunning -and $IsTargetInstance) {
    Write-Host "  Nothing to do — PKB Chrome is ready."
    Write-Host "  Profile: $DebugUserData"
    exit 0
}

if ($AlreadyRunning) {
    Write-Host "⚠️  Port $DebugPort is already in use by another process."
    Write-Host "   To use a different port, set `$env:CHROME_DEBUG_PORT` and update .mcp.json."
    Write-Host "   Otherwise, close other Chrome instances and re-run."
    exit 1
}

# ── Launch Chrome ────────────────────────────────────────────────
if (-not $Silent) {
    Write-Host ""
    Write-Host "🚀 Chrome will open with remote debugging on $DebugUrl."
    Write-Host "   Profile: $DebugUserData"
    Write-Host "   After launch: log into CNKI (知网) in this Chrome window."
    Write-Host "   Login state will be preserved in .pkb-local/chrome-profile/"
    Write-Host ""
}

Write-Host "🚀 Launching PKB Chrome with --remote-debugging-port=$DebugPort..."
try {
    $chromeArgs = @(
        "--remote-debugging-port=$DebugPort",
        "--user-data-dir=`"$DebugUserData`"",
        "--no-first-run",
        "--no-default-browser-check",
        "--no-service-autorun"
    )
    Start-Process -FilePath $ChromeExe -ArgumentList $chromeArgs -WindowStyle Normal
    Start-Sleep -Seconds 3
} catch {
    Write-Host "❌ Failed to launch Chrome: $_"
    exit 1
}

# ── Verify ──────────────────────────────────────────────────────
$maxWait = 15
$waited = 0
while ($waited -lt $maxWait) {
    try {
        $response = Invoke-WebRequest -Uri "$DebugUrl/json" -TimeoutSec 3 -UseBasicParsing
        $pages = $response.Content | ConvertFrom-Json
        if ($pages -is [array] -and $pages.Count -gt 0) {
            Write-Host "✅ PKB Chrome debug confirmed active ($($pages.Count) page(s))."
            Write-Host ""
            Write-Host "📌 Next steps:"
            Write-Host "   1. Log into CNKI (知网) in this Chrome window"
            Write-Host "   2. Start Claude Code: claude --mcp-config .mcp.json"
            Write-Host "   3. Or: .\pkb.ps1 resume"
            Write-Host "   4. Run: /pkb-cnki fill-gaps"
            Write-Host ""
            Write-Host "💡 Login state saved in: $DebugUserData"
            Write-Host "   This directory is in .gitignore — never committed."
            exit 0
        }
    } catch {
        # Still waiting
    }
    Start-Sleep -Seconds 1
    $waited++
}

Write-Host "⚠️  Chrome launched but debug endpoint not confirmed after ${maxWait}s."
Write-Host "   Check manually: curl $DebugUrl/json"
exit 1
