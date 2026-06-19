# hey claude

Local, hands-free **"Hey Claude"** voice control for the terminal. Say the wake word, talk, and your
words either land in the **live Claude Code CLI session** (text mode) or get answered **out loud** (voice
mode). Wake-word detection, speech-to-text, and text-to-speech all run **locally** — only Claude itself
is remote (via the Claude Code CLI you already have).

> **Pasting this repo to an AI to set up?** Start with [`index.md`](index.md) — it's an OKF knowledge
> bundle that explains the app, how it works, the prerequisites, and exactly how to install it.

## How it works

```
mic (parecord)
   │
   ▼
openWakeWord ──"hey claude"?──▶ faster-whisper (base.en)  speech → text
   │  no                                │
   └─ keep listening                    ▼
                          ┌─────────────┴─────────────┐
                  text mode │                           │ voice mode
                            ▼                           ▼
            type into live kitty terminal      headless `claude -p`
            (kitty @ send-text, auto-submit)    + Piper TTS spoken reply
                                                ("confirm" gate before actions)
```

Details in [knowledge/architecture.md](knowledge/architecture.md).

## Platforms

- **Linux — tested & working.**
- **macOS — experimental, ⚠️ NOT YET TESTED on a real Mac.** Audio uses `sounddevice` + `afplay`
  instead of PipeWire; everything else is cross-platform. Best-effort until verified — see
  [knowledge/install-and-run.md](knowledge/install-and-run.md#macos-experimental--untested).
- **Windows** — not supported.

## What you need

Python 3.10+ (or `uv`) · **Claude Code CLI installed & logged in** · **kitty** or **tmux** (for text mode) ·
a mic (+ speakers for voice mode) · internet for the first install.
**Linux:** PipeWire/PulseAudio. **macOS:** grant the terminal Microphone permission.
Full table: [knowledge/install-and-run.md](knowledge/install-and-run.md).

## Install (one command)

```bash
git clone https://github.com/PinkPantr/hey-claude.git ~/claude-voice
cd ~/claude-voice
./install.sh
```
This builds the venv, installs deps, places the **bundled** models (wake word, Piper voice, feature
models), fetches the whisper model, and installs the `claude-voice` launcher + the `/claude-voice` skill.

For **text mode**, enable kitty remote control in `~/.config/kitty/kitty.conf`:
```
allow_remote_control socket-only
listen_on unix:/tmp/kitty
```
then restart kitty once.

## Use

```bash
claude-voice devices    # list mics / output sinks
claude-voice start      # start listening  (or run the /claude-voice skill)
claude-voice test wake  # sanity-check a stage: mic | wake | stt | tts | claude
claude-voice stop
```
Say **"hey claude"**, then speak. Spoken controls: **"switch to text/voice"**, **"stop listening"**.

## What's in here

```
index.md            OKF entry point for AI agents
knowledge/          OKF docs: overview, architecture, install, configuration, wake-word
claude_voice.py     the daemon
install.sh          one-command setup
config.json         runtime config         (see knowledge/configuration.md)
SKILL.md            the /claude-voice Claude Code skill
models/             hey_claude.onnx (trained wake word) + oww-features/ (feature models)
voices/             Piper TTS voice
```

Linux is tested; macOS is experimental and **not yet tested on real hardware**; Windows is unsupported.
The wake-word *training* process is intentionally not in this repo — this is the finished product
(see [knowledge/wake-word.md](knowledge/wake-word.md)).
