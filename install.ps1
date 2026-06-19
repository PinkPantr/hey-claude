# install.ps1 — Windows setup for the "hey claude" voice assistant.
#   ⚠️ EXPERIMENTAL / NOT YET TESTED on real Windows hardware. Please verify and report issues.
#
# Run from the cloned repo:
#   powershell -ExecutionPolicy Bypass -File install.ps1
#
# Mirrors install.sh: venv -> pip deps -> bundled openWakeWord feature models -> whisper fetch ->
# claude-voice.cmd launcher (on PATH) -> /claude-voice skill. VOICE_HOME stays = the repo dir
# (so models/, voices/, config.json live in the repo, like the Linux install).
$ErrorActionPreference = 'Stop'

$RepoDir  = $PSScriptRoot                                          # repo root = VOICE_HOME
$AppHome  = Join-Path $env:LOCALAPPDATA 'claude-voice'             # venv + state (writable)
$VenvDir  = Join-Path $AppHome 'venv'
$VenvPy   = Join-Path $VenvDir 'Scripts\python.exe'
$BinDir   = Join-Path $env:LOCALAPPDATA 'Programs\claude-voice\bin'  # our own dir to add to PATH
$SkillDst = Join-Path $env:USERPROFILE '.claude\skills\claude-voice'

function Say($m)  { Write-Host "`n[install] $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "[warn] $m" -ForegroundColor Yellow }
# native (.exe) failures do NOT throw under $ErrorActionPreference='Stop' in PowerShell 5.1 — check explicitly
function Check($what) { if ($LASTEXITCODE -ne 0) { throw "$what failed (exit $LASTEXITCODE)" } }

Say "Windows audio path is EXPERIMENTAL / untested — verify on real hardware and report issues."
New-Item -ItemType Directory -Force -Path $AppHome, $BinDir, $SkillDst | Out-Null

# --- 1. prerequisites ------------------------------------------------------
if (-not (Get-Command claude  -ErrorAction SilentlyContinue)) { Warn "Claude Code CLI ('claude') not found — install it and run 'claude' once to log in. The assistant drives it." }
if (-not (Get-Command wezterm -ErrorAction SilentlyContinue)) { Warn "WezTerm not found — recommended for TEXT mode. Install:  winget install wez.wezterm  (voice mode works without it)." }

# --- 2. venv pinned to Python >=3.11 (onnxruntime >=1.27 requires >=3.11) ----
Say "Creating venv at $VenvDir (Python >=3.11) ..."
# Don't assume the `py` launcher implies 3.11 is installed (a box may have only 3.12/3.13, or 3.10).
# Probe candidates, verify the version is >=3.11, create the venv with the first that qualifies.
$candidates = @()
if (Get-Command py     -ErrorAction SilentlyContinue) { $candidates += ,@('py','-3.11'); $candidates += ,@('py','-3.12'); $candidates += ,@('py','-3.13'); $candidates += ,@('py','-3') }
if (Get-Command python -ErrorAction SilentlyContinue) { $candidates += ,@('python') }
$made = $false
foreach ($c in $candidates) {
    $exe = $c[0]; $a = @($c[1..($c.Length-1)])
    $ver = & $exe @a -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $ver) { continue }
    $p = $ver.Trim().Split('.')
    if ([int]$p[0] -ne 3 -or [int]$p[1] -lt 11) { Warn "Skipping '$exe $($a -join ' ')' — Python $($ver.Trim()) is < 3.11."; continue }
    Say "Using '$exe $($a -join ' ')' (Python $($ver.Trim())) ..."
    & $exe @a -m venv $VenvDir
    if ($LASTEXITCODE -eq 0 -and (Test-Path $VenvPy)) { $made = $true; break }
    Warn "venv creation with '$exe $($a -join ' ')' failed — trying next."
}
if (-not $made -or -not (Test-Path $VenvPy)) { throw "No Python >=3.11 found (onnxruntime needs it). Install Python 3.11/3.12/3.13 and re-run." }

# --- 3. deps (piper-tts>=1.4 ships a Windows wheel; sounddevice = mic backend) ---
Say "Installing Python deps (faster-whisper, openwakeword, piper-tts>=1.4, sounddevice) ..."
& $VenvPy -m pip install --upgrade pip;                                          Check 'pip upgrade'
& $VenvPy -m pip install faster-whisper openwakeword "piper-tts>=1.4" sounddevice; Check 'pip install (deps)'

# --- 4. bundled openWakeWord feature models -> into the venv (no download) ---
Say "Installing bundled openWakeWord feature models ..."
$OwwDir = & $VenvPy -c "import os,openwakeword; print(os.path.join(os.path.dirname(openwakeword.__file__),'resources','models'))"
New-Item -ItemType Directory -Force -Path $OwwDir | Out-Null
Copy-Item (Join-Path $RepoDir 'models\oww-features\*.onnx') $OwwDir -Force

# --- 5. whisper base.en (the one download; >100MB, can't ship in git) -------
Say "Prefetching whisper base.en (~140MB, one-time) ..."
try {
    & $VenvPy -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8'); print('whisper base.en cached')"
} catch { Warn "whisper prefetch failed — it will download on first run instead." }

# --- 6. launcher: claude-voice.cmd on PATH ----------------------------------
Say "Installing launcher -> $BinDir\claude-voice.cmd"
$cmdContent = @"
@echo off
set "VOICE_HOME=$RepoDir"
"$VenvPy" "$RepoDir\claude_voice.py" %*
"@
# OEM (console codepage), NOT ASCII: the embedded venv path is under C:\Users\<name>\... — an
# accented username would become '?' under ASCII and break the launcher. (UTF8 would add a BOM
# that corrupts the `@echo off` line in PowerShell 5.1.)
Set-Content -Path (Join-Path $BinDir 'claude-voice.cmd') -Value $cmdContent -Encoding OEM

$userPath = [Environment]::GetEnvironmentVariable('Path','User')
if (($userPath -split ';') -notcontains $BinDir) {
    $newPath = if ([string]::IsNullOrEmpty($userPath)) { $BinDir } else { "$userPath;$BinDir" }
    [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')   # persists (registry) + broadcasts
    $env:Path = "$env:Path;$BinDir"
    Say "Added $BinDir to user PATH — RESTART terminals to pick it up."
}

# --- 7. skill ---------------------------------------------------------------
Copy-Item (Join-Path $RepoDir 'SKILL.md') (Join-Path $SkillDst 'SKILL.md') -Force

Say "Done. Quick check:  claude-voice devices"
Write-Host @"

Windows next steps (EXPERIMENTAL — untested):
  - Microphone permission: Settings -> Privacy & security -> Microphone -> "Let desktop apps access
    your microphone" = On. If 'claude-voice test mic' shows near-silence, that's the cause.
  - TEXT mode: run Claude Code inside WezTerm (winget install wez.wezterm). The /claude-voice skill
    auto-detects `$env:WEZTERM_PANE` and injects with 'wezterm cli send-text'.
  - Start:  claude-voice start   (or run the /claude-voice skill).  Say "hey claude", then speak.
  - Spoken replies (voice mode) use the system default output device.
"@
