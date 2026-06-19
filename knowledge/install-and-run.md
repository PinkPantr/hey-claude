---
type: concept
title: Installing and running hey claude
description: Prerequisites the user must have, what install.sh does, how to run it, and troubleshooting. Linux only for now.
timestamp: 2026-06-18T22:00:00-04:00
status: active
---

# Prerequisites (what the user must have)

The repo ships the bespoke + large assets (wake model, Piper voice, feature models, all scripts). The
user/agent must provide these standard, easy-to-get pieces:

| Requirement | Why | Notes |
|---|---|---|
| **Linux** | audio capture + terminal injection are Linux-specific here | macOS/Windows = future work |
| **PipeWire or PulseAudio** (`parecord`) | microphone capture | `pipewire-pulse` on most distros |
| **Python 3.10** (or `uv`) | the isolated venv | installer prefers `uv` if present |
| **Claude Code CLI** (`claude`), logged in | the assistant drives Claude | run `claude` once to authenticate; needs an Anthropic plan/key |
| **kitty terminal** | TEXT mode injects into the live kitty window | only needed for text mode; voice mode works without it |
| **A microphone and speakers** | input + spoken output | pick exact devices with `claude-voice devices` |
| **Internet (first install only)** | pip packages + the whisper model download | everything else is bundled |

# What install.sh does

```bash
git clone https://github.com/PinkPantr/hey-claude.git ~/claude-voice
cd ~/claude-voice
./install.sh
```

It (idempotently): checks prerequisites; creates the venv at `~/.venvs/voice`; pip-installs
`faster-whisper`, `openwakeword`, `piper-tts`; copies the **bundled** openWakeWord feature models into
the venv (no download); prefetches the **whisper `base.en`** model (the only download — it is >100MB so
it cannot ship in git); installs the `claude-voice` launcher to `~/.local/bin`; and installs the
`/claude-voice` skill to `~/.claude/skills/claude-voice/`.

# Enable text mode (kitty remote control)

In `~/.config/kitty/kitty.conf`:
```
allow_remote_control socket-only
listen_on unix:/tmp/kitty
```
Then **fully restart kitty once**. The `/claude-voice` skill reads `KITTY_LISTEN_ON` / `KITTY_WINDOW_ID`
from the environment and wires injection automatically.

# Run

```bash
claude-voice devices        # list mics / output sinks, then set them in config.json if needed
claude-voice start          # start listening (uses config.json)
# or, inside Claude Code:   run the /claude-voice skill (interactive: mic → output → mode)
claude-voice test wake      # sanity-check each stage: mic | wake | stt | tts | claude
claude-voice stop
```
Say **"hey claude"**, then speak. Spoken controls: "switch to text/voice", "stop listening".

# Troubleshooting

- **`~/.local/bin` not on PATH** → `export PATH="$HOME/.local/bin:$PATH"`.
- **No wake trigger** → check `claude-voice test mic` and the right `input_source` in config; lower
  `wake_threshold` slightly (e.g. 0.4).
- **Text mode does nothing** → kitty remote control not active; confirm `kitty.conf` lines and that you
  restarted kitty (`echo $KITTY_LISTEN_ON` should be set).
- **Voice mode silent** → `claude-voice test tts`; confirm a `.onnx` voice exists in `voices/` and
  `piper` is in the venv.
- **`claude` not found** → install the Claude Code CLI and run it once to log in.
