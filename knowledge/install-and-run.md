---
type: concept
title: Installing and running hey claude
description: Prerequisites, what install.sh does, how to run it, troubleshooting. Linux is tested; macOS is experimental and NOT YET TESTED on real hardware.
timestamp: 2026-06-19T13:00:00-04:00
status: active
---

# Platform support

- **Linux — tested and working.** Mic via PipeWire/PulseAudio (`parecord`), playback via `paplay`.
- **macOS — experimental, NOT YET TESTED on a real Mac.** The audio layer falls back to
  `sounddevice` (mic + device list) and `afplay` (playback); everything else (wake model, Whisper,
  Piper, kitty/tmux inject, Claude CLI) is cross-platform. Treat it as best-effort until verified —
  please report what works/breaks. See the macOS section below.
- **Windows** — not yet a full port (audio + daemon process-control still need Windows work), BUT the
  hard part — text-mode injection — is **solved**: the `wezterm` backend (`wezterm cli send-text`) runs
  natively on Windows. So a Windows port is now realistic; it just hasn't been built/tested.

# Prerequisites (what the user must provide)

The repo ships the bespoke + large assets (wake model, Piper voice, feature models, all scripts).
You provide these standard pieces:

**Both platforms**
| Requirement | Why |
|---|---|
| **Python 3.10+** (or `uv`) | the isolated venv |
| **Claude Code CLI** (`claude`), logged in | the assistant drives Claude (needs an Anthropic plan/key) |
| **WezTerm** (recommended) *or* **kitty** (with remote control) *or* **tmux** | TEXT mode only — injecting into the live CLI. WezTerm is the cross-platform pick (and the path that also works on Windows). voice mode needs none of these |
| **A microphone** (+ speakers for voice mode) | input / spoken output |
| **Internet (first install only)** | pip packages + the whisper model download |

**Linux:** PipeWire or PulseAudio (`parecord`/`paplay`/`pactl`) — present on every modern desktop distro.
**macOS:** `afplay` (built in) + `sounddevice` (installed by `install.sh`). **Grant the terminal Microphone permission** (see below).

# What install.sh does

```bash
git clone https://github.com/PinkPantr/hey-claude.git ~/claude-voice
cd ~/claude-voice
./install.sh
```

Idempotently: detects the OS; creates the venv at `~/.venvs/voice`; pip-installs `faster-whisper`,
`openwakeword`, `piper-tts>=1.4` (**+ `sounddevice` on macOS**); copies the **bundled** openWakeWord
feature models into the venv (no download); prefetches the **whisper `base.en`** model (the only
download — >100MB, can't ship in git); installs the `claude-voice` launcher and the `/claude-voice` skill.

# Enable text mode

Run Claude Code inside one of these terminals; the `/claude-voice` skill auto-detects which:
- **WezTerm (recommended, all platforms incl. Windows)** — no setup. Its CLI remote control is on by
  default; the skill uses `$WEZTERM_PANE` (this session's pane) as the inject target.
- **kitty** — add to `~/.config/kitty/kitty.conf`:
  ```
  allow_remote_control socket-only
  listen_on unix:/tmp/kitty
  ```
  then **fully restart kitty once**.
- **tmux** — works out of the box (`send-keys`).

Note: if you launch one terminal from inside another (e.g. WezTerm from a kitty shell), the inner
terminal inherits the outer's `KITTY_LISTEN_ON`/`TMUX_PANE` — the skill uses `TERM_PROGRAM`/`TERM` to
pick the terminal you're *actually* in and ignores those stale vars.

# Run

```bash
claude-voice devices        # list mics / output sinks (your machine's own hardware)
claude-voice test mic       # confirm the mic is actually capturing (RMS level)
claude-voice start          # start listening (uses config.json)
# or, inside Claude Code:   run the /claude-voice skill (interactive: mic → output → mode)
claude-voice stop
```
Say **"hey claude"**, then speak. Spoken controls: "switch to text/voice", "stop listening".

# macOS (experimental — untested)

> ⚠️ **This path has not been run on a real Mac yet.** It's implemented and reviewed but unverified.

- **Microphone permission is the #1 gotcha.** macOS attaches mic permission to the **terminal app**, not
  to Python. If permission isn't granted, capture returns **silent zeros with no error** — the daemon
  would look like it's listening but never wake. The daemon and `claude-voice test mic` detect sustained
  silence and print a hint. To fix: **System Settings → Privacy & Security → Microphone → enable your
  terminal (Terminal/iTerm/kitty), then relaunch it.** Run it **attached** the first time so the
  permission prompt can appear (a detached/backgrounded process may not get it).
- **Output device selection isn't supported** on macOS — spoken replies use the system default output
  (`afplay`). Set your default output in System Settings.
- **Apple Silicon**: the models run CPU-only (no GPU), which is fine for this workload.
- **Do NOT `brew install portaudio`** — `sounddevice`'s wheel bundles it; a brew copy can shadow it.

# Troubleshooting

- **`~/.local/bin` not on PATH** → `export PATH="$HOME/.local/bin:$PATH"`.
- **No wake trigger** → `claude-voice test mic` (is RMS > ~400 when you speak?); check `input_source`;
  lower `wake_threshold` slightly (e.g. 0.4).
- **macOS: mic silent / never wakes** → terminal lacks Microphone permission (see macOS section); grant it
  and relaunch the terminal.
- **Text mode does nothing** → kitty remote control not active; confirm the `kitty.conf` lines and that you
  restarted kitty (`echo $KITTY_LISTEN_ON` should be set), or use tmux.
- **Voice mode silent** → `claude-voice test tts`; confirm a `.onnx` voice exists in `voices/` and `piper`
  is in the venv (macOS: `piper-tts>=1.4`).
- **`claude` not found** → install the Claude Code CLI and run it once to log in.
