# pkb.ps1 — PKB Unified Launcher (Session Continuity & MCP Bootstrap)
#
# Usage:
#   .\pkb.ps1                  # Default: environment check + session start
#   .\pkb.ps1 status           # Show PKB status summary
#   .\pkb.ps1 cnki             # Full CNKI workflow (Chrome + MCP + session)
#   .\pkb.ps1 doctor           # Run comprehensive diagnostics
#   .\pkb.ps1 resume           # Resume last Claude Code session with MCP
#
# What it does (default):
#   1. Verify PKB root
#   2. Check Python, Node, npx, Chrome
#   3. Ensure Chrome debug instance is running
#   4. Verify .mcp.json is present
#   5. Verify chrome-devtools MCP can connect
#   6. Read active task state
#   7. Print ready-to-use summary

param(
    [string]$Command = "start"
)

$ErrorActionPreference = "Stop"
$PKB_ROOT = $env:PKB_ROOT
if (-not $PKB_ROOT) {
    $PKB_ROOT = Split-Path -Parent $MyInvocation.ScriptName
}

$DebugPort = 9222
$DebugHost = $env:CHROME_DEBUG_HOST
if (-not $DebugHost) { $DebugHost = "127.0.0.1" }
$DebugUrl = "http://${DebugHost}:${DebugPort}"

$LocalDir = Join-Path $PKB_ROOT ".pkb-local"
$ChromeProfileDir = Join-Path $LocalDir "chrome-profile"
$LogDir = Join-Path $LocalDir "logs"

# ── Helper functions ────────────────────────────────────────────

function Write-Status {
    param([string]$Icon, [string]$Status, [string]$Message)
    Write-Host "  [$Status] $Icon $Message"
}

function Test-Command {
    param([string]$Cmd, [string]$Args = "--version")
    try {
        $result = & $Cmd $Args 2>&1
        if ($LASTEXITCODE -eq 0) {
            return $true, ($result -join " ")[0..80] -join ""
        }
        return $false, "exit code $LASTEXITCODE"
    } catch {
        return $false, "not found"
    }
}

function Test-Port {
    param([int]$Port, [string]$Host = "127.0.0.1")
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect($Host, $Port)
        $tcp.Close()
        return $true
    } catch {
        return $false
    }
}

function Test-ChromeDebugEndpoint {
    param([string]$Url = $DebugUrl)
    try {
        $response = Invoke-WebRequest -Uri "$Url/json" -TimeoutSec 3 -UseBasicParsing
        $data = $response.Content | ConvertFrom-Json
        if ($data -is [array] -and $data.Count -gt 0) {
            return $true, "$($data.Count) page(s)"
        }
        return $false, "no debuggable pages"
    } catch {
        return $false, $_.Exception.Message
    }
}

function Find-Chrome {
    $paths = @(
        "C:\Program Files\Google\Chrome\Application\chrome.exe",
        "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) { return $p }
    }
    $cmd = (Get-Command "chrome.exe" -ErrorAction SilentlyContinue).Source
    if ($cmd) { return $cmd }
    $cmd = (Get-Command "chrome" -ErrorAction SilentlyContinue).Source
    if ($cmd) { return $cmd }
    return $null
}

function Start-ChromeDebug {
    param([string]$ChromeExe, [string]$ProfileDir)
    Write-Host ""
    Write-Host "🚀 Starting Chrome with remote debugging on $DebugUrl ..."
    Write-Host "   Profile: $ProfileDir"

    # Ensure profile directory exists
    if (-not (Test-Path $ProfileDir)) {
        New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null
    }

    $args = @(
        "--remote-debugging-port=$DebugPort",
        "--user-data-dir=`"$ProfileDir`"",
        "--no-first-run",
        "--no-default-browser-check",
        "--no-service-autorun"
    )

    try {
        Start-Process -FilePath $ChromeExe -ArgumentList $args -WindowStyle Normal
        # Wait for Chrome to start
        $waited = 0
        while ($waited -lt 15) {
            Start-Sleep -Seconds 1
            $waited++
            if (Test-Port -Port $DebugPort -Host $DebugHost) {
                Write-Status "PASS" "✅" "Chrome debug port active after ${waited}s"
                return $true
            }
        }
        Write-Status "WARN" "⚠️" "Chrome started but debug port not detected after 15s"
        return $false
    } catch {
        Write-Status "FAIL" "❌" "Failed to launch Chrome: $_"
        return $false
    }
}

# ── Commands ────────────────────────────────────────────────────

function Invoke-Status {
    Write-Host ""
    Write-Host "══════════════════════════════════════════════════"
    Write-Host "  PKB Status — $PKB_ROOT"
    Write-Host "══════════════════════════════════════════════════"

    # Python
    $ok, $ver = Test-Command "python" "--version"
    Write-Status $(if ($ok) { "PASS" } else { "FAIL" }) $(if ($ok) { "✅" } else { "❌" }) "Python: $ver"

    # Node
    $ok, $ver = Test-Command "node" "--version"
    Write-Status $(if ($ok) { "PASS" } else { "FAIL" }) $(if ($ok) { "✅" } else { "❌" }) "Node.js: $ver"

    # npx
    $ok, $ver = Test-Command "npx" "--version"
    Write-Status $(if ($ok) { "PASS" } else { "FAIL" }) $(if ($ok) { "✅" } else { "❌" }) "npx: $ver"

    # Bun (optional)
    $ok, $ver = Test-Command "bun" "--version"
    Write-Status $(if ($ok) { "PASS" } else { "WARN" }) $(if ($ok) { "✅" } else { "⚠️" }) "Bun: $(if ($ok) { $ver } else { 'not installed (optional)' })"

    # Chrome
    $chrome = Find-Chrome
    if ($chrome) {
        Write-Status "PASS" "✅" "Chrome: $chrome"
    } else {
        Write-Status "FAIL" "❌" "Chrome: not found"
    }

    # Chrome debug
    $portOk = Test-Port -Port $DebugPort -Host $DebugHost
    if ($portOk) {
        $ok, $detail = Test-ChromeDebugEndpoint
        Write-Status $(if ($ok) { "PASS" } else { "WARN" }) $(if ($ok) { "✅" } else { "⚠️" }) "Chrome debug: $detail"
    } else {
        Write-Status "FAIL" "❌" "Chrome debug port $DebugPort not open"
    }

    # .mcp.json
    $mcp = Join-Path $PKB_ROOT ".mcp.json"
    if (Test-Path $mcp) {
        Write-Status "PASS" "✅" ".mcp.json: found"
    } else {
        Write-Status "FAIL" "❌" ".mcp.json: not found"
    }

    # Active task
    $taskFile = Join-Path $LocalDir "state" "active-task.json"
    if (Test-Path $taskFile) {
        Write-Status "PASS" "✅" "Active task: found ($taskFile)"
    } else {
        Write-Status "WARN" "⚠️" "No active task"
    }

    Write-Host "══════════════════════════════════════════════════"

    # Show task if exists
    if (Test-Path $taskFile) {
        python "$PKB_ROOT\tools\pkb_task.py" show
    }
}

function Invoke-Cnki {
    Write-Host ""
    Write-Host "══════════════════════════════════════════════════"
    Write-Host "  PKB CNKI Workflow — Chrome + MCP Bootstrap"
    Write-Host "══════════════════════════════════════════════════"

    # Step 1: Find Chrome
    $chrome = Find-Chrome
    if (-not $chrome) {
        Write-Host "❌ Chrome not found. Please install Google Chrome."
        Write-Host "   Download: https://www.google.com/chrome/"
        exit 1
    }
    Write-Status "PASS" "✅" "Chrome: $chrome"

    # Step 2: Check debug port
    $portOk = Test-Port -Port $DebugPort -Host $DebugHost
    $debugReady = $false
    if ($portOk) {
        $ok, $detail = Test-ChromeDebugEndpoint
        if ($ok) {
            Write-Status "PASS" "✅" "Chrome debug ready: $detail"
            $debugReady = $true
        } else {
            Write-Status "WARN" "⚠️" "Port $DebugPort open but not a Chrome debug instance: $detail"
            Write-Host "   Will start a new PKB Chrome instance."
        }
    }

    if (-not $debugReady) {
        # Step 3: Start Chrome with debug
        if (-not (Test-Path $ChromeProfileDir)) {
            New-Item -ItemType Directory -Path $ChromeProfileDir -Force | Out-Null
        }
        $started = Start-ChromeDebug -ChromeExe $chrome -ProfileDir $ChromeProfileDir
        if (-not $started) {
            Write-Host "❌ Failed to start Chrome debug instance."
            Write-Host "   Try: .\pkb.ps1 doctor"
            exit 1
        }
    }

    # Step 4: Verify .mcp.json
    $mcp = Join-Path $PKB_ROOT ".mcp.json"
    if (-not (Test-Path $mcp)) {
        Write-Status "FAIL" "❌" ".mcp.json missing at project root"
        Write-Host "   Run: .\pkb.ps1 doctor for diagnosis"
        exit 1
    }
    Write-Status "PASS" "✅" ".mcp.json ready"

    # Step 5: Print next steps
    Write-Host ""
    Write-Host "══════════════════════════════════════════════════"
    Write-Host "  CNKI Workflow Ready"
    Write-Host "══════════════════════════════════════════════════"
    Write-Host ""
    Write-Host "  📌 Next steps:"
    Write-Host "   1. Log into CNKI (知网) in the PKB Chrome window"
    Write-Host "   2. Start Claude Code: claude --mcp-config .mcp.json"
    Write-Host "   3. Or resume session:  .\pkb.ps1 resume"
    Write-Host "   4. In Claude Code, run: /pkb-cnki fill-gaps"
    Write-Host ""
    Write-Host "  💡 Chrome profile saved at: $ChromeProfileDir"
    Write-Host "     (login state persists, never committed to Git)"
    Write-Host ""

    # Step 6: Print task state if exists
    $taskFile = Join-Path $LocalDir "state" "active-task.json"
    if (Test-Path $taskFile) {
        python "$PKB_ROOT\tools\pkb_task.py" show
    }
}

function Invoke-Doctor {
    python "$PKB_ROOT\tools\pkb_doctor.py" $args
}

function Invoke-Resume {
    Write-Host ""
    Write-Host "══════════════════════════════════════════════════"
    Write-Host "  PKB Session Resume"
    Write-Host "══════════════════════════════════════════════════"

    # Check if already in Claude Code session
    if ($env:CLAUDE_CODE_SESSION) {
        Write-Host "⚠️  Already in a Claude Code session."
        Write-Host "   Use /clear to reset or exit and re-run."
        exit 0
    }

    # Show active task
    $taskFile = Join-Path $LocalDir "state" "active-task.json"
    if (Test-Path $taskFile) {
        Write-Host ""
        python "$PKB_ROOT\tools\pkb_task.py" show
    } else {
        Write-Status "WARN" "⚠️" "No active task — starting fresh session"
    }

    # Check MCP
    $mcp = Join-Path $PKB_ROOT ".mcp.json"
    $mcpFlag = ""
    if (Test-Path $mcp) {
        Write-Status "PASS" "✅" ".mcp.json found — will load MCP"
        $mcpFlag = "--mcp-config .mcp.json"
    }

    # Check Chrome
    $portOk = Test-Port -Port $DebugPort -Host $DebugHost
    if (-not $portOk) {
        Write-Status "WARN" "⚠️" "Chrome debug port not open — run .\pkb.ps1 cnki first"
    } else {
        Write-Status "PASS" "✅" "Chrome debug port active"
    }

    # Try Claude Code continue
    Write-Host ""
    Write-Host "  Starting Claude Code with session resume..."
    Write-Host "  Command: claude --continue $mcpFlag"
    Write-Host ""

    try {
        & claude --continue @($mcpFlag -split ' ' | Where-Object { $_ }) 2>&1
    } catch {
        Write-Host "⚠️  claude --continue failed, trying regular start..."
        try {
            & claude @($mcpFlag -split ' ' | Where-Object { $_ }) 2>&1
        } catch {
            Write-Host "❌ Failed to start Claude Code."
            Write-Host "   Check: claude --help"
            exit 1
        }
    }
}

function Invoke-Start {
    Write-Host ""
    Write-Host "══════════════════════════════════════════════════"
    Write-Host "  PKB v0.6.10-alpha — Code Review Hardening & Web Pack Fix"
    Write-Host "══════════════════════════════════════════════════"
    Write-Host ""

    # Run status
    Invoke-Status

    # Quick pre-flight
    $mcp = Join-Path $PKB_ROOT ".mcp.json"
    if (-not (Test-Path $mcp)) {
        Write-Host ""
        Write-Status "FAIL" "❌" ".mcp.json missing — MCP will not load in Claude Code"
        Write-Host "   Create one with chrome-devtools configuration."
    }

    Write-Host ""
    Write-Host "  Commands:"
    Write-Host "    .\pkb.ps1           This screen"
    Write-Host "    .\pkb.ps1 status    Status summary"
    Write-Host "    .\pkb.ps1 cnki      Full CNKI workflow"
    Write-Host "    .\pkb.ps1 doctor    Comprehensive diagnostics"
    Write-Host "    .\pkb.ps1 resume    Resume Claude Code session"
    Write-Host ""
}

# ── Main ────────────────────────────────────────────────────────

switch ($Command) {
    "status"  { Invoke-Status }
    "cnki"    { Invoke-Cnki }
    "doctor"  { Invoke-Doctor }
    "resume"  { Invoke-Resume }
    "start"   { Invoke-Start }
    default   { Invoke-Start }
}
