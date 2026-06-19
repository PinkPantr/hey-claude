#!/usr/bin/env bash
# install.sh — one-command setup for the "hey claude" voice assistant.
#
#   Linux : tested.
#   macOS : BEST-EFFORT / UNTESTED — audio uses `sounddevice` + `afplay` instead of
#           parecord/paplay. Please verify on a real Mac and report issues.
#
# Steps: venv (~/.venvs/voice) → pip deps → bundled openWakeWord feature models →
# whisper fetch → launcher + /claude-voice skill. The Piper TTS voice and the trained
# hey_claude wake word ship IN this repo.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HOME/.venvs/voice"
PY="$VENV/bin/python"
SKILL_DST="$HOME/.claude/skills/claude-voice"
LAUNCHER="$HOME/.local/bin/claude-voice"
OS="$(uname -s)"

say()  { printf '\n\033[1;36m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }

# ── 1. prerequisites (per OS) ──────────────────────────────────────────────
say "Checking prerequisites ($OS) …"
command -v claude >/dev/null || warn "Claude Code CLI ('claude') not found — install it and run 'claude' once to log in. The assistant drives it."
command -v kitty  >/dev/null || warn "kitty not found — needed for TEXT mode (live-CLI inject). voice mode works without it."
case "$OS" in
  Linux)
    command -v parecord >/dev/null || warn "parecord not found — install PipeWire/PulseAudio (e.g. pipewire-pulse) for mic + playback."
    ;;
  Darwin)
    warn "macOS audio path is UNTESTED (sounddevice + afplay). Verify on real hardware and report issues."
    command -v afplay >/dev/null || warn "afplay missing?! (it ships with macOS) — TTS playback needs it."
    ;;
  *)
    warn "Unsupported OS '$OS' — only Linux is tested; macOS is best-effort."
    ;;
esac

# ── 2. venv (Python ≥3.10 via uv, else a system python ≥3.10) ──────────────
say "Creating venv at $VENV …"
if command -v uv >/dev/null; then
  uv venv --python 3.10 "$VENV" || { echo "venv creation failed"; exit 1; }
  PIP_INSTALL=(uv pip install --python "$PY")
else
  PYBIN="$(command -v python3.10 || true)"
  if [ -z "$PYBIN" ] && command -v python3 >/dev/null && python3 -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,10) else 1)'; then
    PYBIN="$(command -v python3)"
  fi
  [ -n "$PYBIN" ] || { echo "Need Python ≥3.10 (or install 'uv'). macOS: 'brew install python@3.12' or uv."; exit 1; }
  "$PYBIN" -m venv "$VENV"
  PIP_INSTALL=("$PY" -m pip install)
  "$PY" -m pip install -q --upgrade pip
fi

# ── 3. deps ────────────────────────────────────────────────────────────────
say "Installing Python deps (faster-whisper, openwakeword, piper-tts) …"
# piper-tts>=1.4 ships an arm64 macOS wheel with embedded espeak-ng; older versions fail on Apple Silicon.
"${PIP_INSTALL[@]}" faster-whisper openwakeword "piper-tts>=1.4" || { echo "pip install failed"; exit 1; }
if [ "$OS" = "Darwin" ]; then
  # macOS mic capture + device enumeration use sounddevice. Its macOS wheel is universal2
  # (arm64 + Intel) and bundles PortAudio — do NOT 'brew install portaudio' (it would shadow it).
  say "Installing sounddevice (macOS audio backend) …"
  "${PIP_INSTALL[@]}" sounddevice || { echo "sounddevice install failed"; exit 1; }
fi

# ── 4. bundled openWakeWord feature models → into the venv (no download) ────
say "Installing bundled openWakeWord feature models …"
OWW_DIR="$("$PY" -c 'import os,openwakeword; print(os.path.join(os.path.dirname(openwakeword.__file__),"resources","models"))')"
mkdir -p "$OWW_DIR"
cp -f "$REPO"/models/oww-features/*.onnx "$OWW_DIR"/ && echo "  -> $OWW_DIR"

# ── 5. whisper base.en (the one network download — too big for git) ─────────
say "Prefetching whisper base.en (~140MB, one-time) …"
"$PY" - <<'PYEOF' || warn "whisper prefetch failed — it will download on first run instead."
from faster_whisper import WhisperModel
WhisperModel("base.en", device="cpu", compute_type="int8")
print("whisper base.en cached OK")
PYEOF

# ── 6. launcher + skill ─────────────────────────────────────────────────────
say "Installing launcher → $LAUNCHER"
mkdir -p "$(dirname "$LAUNCHER")"
cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
exec env VOICE_HOME="$REPO" "$PY" "$REPO/claude_voice.py" "\$@"
EOF
chmod +x "$LAUNCHER"

say "Installing /claude-voice skill → $SKILL_DST"
mkdir -p "$SKILL_DST"
cp -f "$REPO/SKILL.md" "$SKILL_DST/SKILL.md"

# ── done — OS-specific next steps ────────────────────────────────────────────
say "Done. Quick check:  claude-voice devices"
if [ "$OS" = "Darwin" ]; then
cat <<'EOF'

macOS next steps:
  • Microphone permission: the FIRST time it records, macOS must grant your terminal mic access.
    If capture is silent (no error), enable it: System Settings → Privacy & Security → Microphone
    → turn on your terminal app (Terminal/iTerm/kitty), then RELAUNCH the terminal.
    (A detached/backgrounded process may not get the prompt — run it attached the first time.)
  • Check capture level:  claude-voice test mic
  • For TEXT mode, enable kitty remote control in ~/.config/kitty/kitty.conf:
        allow_remote_control socket-only
        listen_on unix:/tmp/kitty
    then fully restart kitty once.
  • Start:  claude-voice start   (or run the /claude-voice skill).  Say "hey claude", then speak.
  • Note: on macOS, spoken replies use the system default output (per-device output_sink is ignored).
EOF
else
cat <<'EOF'

Next steps:
  • For TEXT mode, enable kitty remote control in ~/.config/kitty/kitty.conf:
        allow_remote_control socket-only
        listen_on unix:/tmp/kitty
    then fully restart kitty once.
  • Start it:  claude-voice start      (or run the /claude-voice skill in Claude Code)
  • Say "hey claude", then speak.
EOF
fi
echo
echo "If ~/.local/bin isn't on your PATH, add:  export PATH=\"\$HOME/.local/bin:\$PATH\""
