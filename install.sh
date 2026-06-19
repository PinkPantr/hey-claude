#!/usr/bin/env bash
# install.sh — one-command setup for the "hey claude" voice assistant (Linux).
#
# What this does (everything an AI/user needs after `git clone`):
#   1. checks prerequisites (python3.10, pipewire/parecord, claude CLI, kitty for text mode)
#   2. builds an isolated venv at ~/.venvs/voice
#   3. pip-installs faster-whisper + openwakeword + piper-tts
#   4. installs the BUNDLED openWakeWord feature models into the venv (no download)
#   5. fetches the whisper base.en STT model (only thing too big to ship in git)
#   6. installs the `claude-voice` launcher and the /claude-voice Claude Code skill
#
# The Piper TTS voice and the trained hey_claude wake word ship IN this repo.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HOME/.venvs/voice"
PY="$VENV/bin/python"
SKILL_DST="$HOME/.claude/skills/claude-voice"
LAUNCHER="$HOME/.local/bin/claude-voice"

say() { printf '\n\033[1;36m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }

# ── 1. prerequisites ───────────────────────────────────────────────────────
say "Checking prerequisites …"
[ "$(uname -s)" = "Linux" ] || { warn "This installer targets Linux. macOS/Windows: not yet supported."; }
command -v parecord >/dev/null || warn "parecord not found — install PipeWire/PulseAudio (pipewire-pulse) for mic capture."
command -v claude   >/dev/null || warn "Claude Code CLI ('claude') not found — install it and run 'claude' once to log in. The assistant drives it."
command -v kitty    >/dev/null || warn "kitty not found — needed for TEXT mode (injecting speech into the live CLI). voice mode works without it."

# python 3.10 (via uv if available, else system python3.10)
say "Creating venv at $VENV …"
if command -v uv >/dev/null; then
  uv venv --python 3.10 "$VENV" || { echo "venv creation failed"; exit 1; }
  PIP_INSTALL=(uv pip install --python "$PY")
else
  PYBIN="$(command -v python3.10 || true)"
  [ -n "$PYBIN" ] || { echo "Need python3.10 (or 'uv'). Install one and re-run."; exit 1; }
  "$PYBIN" -m venv "$VENV"
  PIP_INSTALL=("$PY" -m pip install)
  "$PY" -m pip install -q --upgrade pip
fi

# ── 2. deps ────────────────────────────────────────────────────────────────
say "Installing Python deps (faster-whisper, openwakeword, piper-tts) …"
"${PIP_INSTALL[@]}" faster-whisper openwakeword piper-tts || { echo "pip install failed"; exit 1; }

# ── 3. bundled openWakeWord feature models → into the package (no download) ──
say "Installing bundled openWakeWord feature models …"
OWW_DIR="$("$PY" -c 'import os,openwakeword; print(os.path.join(os.path.dirname(openwakeword.__file__),"resources","models"))')"
mkdir -p "$OWW_DIR"
cp -f "$REPO"/models/oww-features/*.onnx "$OWW_DIR"/ && echo "  -> $OWW_DIR"

# ── 4. whisper base.en (the one network download — too big for git) ─────────
say "Prefetching whisper ${WHISPER:-base.en} (~140MB, one-time) …"
"$PY" - <<PYEOF || warn "whisper prefetch failed — it will download on first run instead."
from faster_whisper import WhisperModel
WhisperModel("base.en", device="cpu", compute_type="int8")
print("whisper base.en cached OK")
PYEOF

# ── 5. launcher + skill ─────────────────────────────────────────────────────
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

# ── done ────────────────────────────────────────────────────────────────────
say "Done. Quick check:  claude-voice devices"
cat <<'EOF'

Next steps:
  • For TEXT mode, enable kitty remote control in ~/.config/kitty/kitty.conf:
        allow_remote_control socket-only
        listen_on unix:/tmp/kitty
    then fully restart kitty once.
  • Start it:   claude-voice start      (or run the /claude-voice skill in Claude Code)
  • Say "hey claude", then speak.

If ~/.local/bin isn't on your PATH, add:  export PATH="$HOME/.local/bin:$PATH"
EOF
