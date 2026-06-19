---
okf_version: "0.1"
---

# hey claude — knowledge bundle

This repository is a working, self-contained **voice assistant for Claude Code** and an **OKF v0.1**
knowledge bundle ([Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog)).
If you are an AI agent setting this up for a user, read the pages below first — they tell you what the
app is, how it works, what the user must have, and exactly how to install and run it.

## Read these (in order)

1. [knowledge/overview.md](knowledge/overview.md) — what the app is and does (`type: project`)
2. [knowledge/architecture.md](knowledge/architecture.md) — how it works, component by component (`type: concept`)
3. [knowledge/install-and-run.md](knowledge/install-and-run.md) — **prerequisites + setup + run** (`type: concept`)
4. [knowledge/configuration.md](knowledge/configuration.md) — every `config.json` field (`type: concept`)
5. [knowledge/wake-word.md](knowledge/wake-word.md) — how wake detection works + the bundled model (`type: concept`)

## Code & assets (the actual product)

- `claude_voice.py` — the daemon (mic → wake → speech-to-text → inject/claude → speech)
- `install.sh` — one command: venv, deps, places bundled models, fetches whisper, installs launcher + skill
- `config.json` — runtime configuration
- `SKILL.md` — the `/claude-voice` Claude Code skill (interactive launcher)
- `models/hey_claude.onnx` — the trained "hey claude" wake-word model (bundled)
- `models/oww-features/` — openWakeWord feature models (bundled; installer copies into the venv)
- `voices/` — the Piper TTS voice (bundled)

## TL;DR for an agent

```bash
./install.sh          # sets everything up (needs internet for pip + whisper)
claude-voice devices  # verify mic/speakers
claude-voice start    # or run the /claude-voice skill
```
Then the user says **"hey claude"** and speaks. See `knowledge/install-and-run.md` for prerequisites
(Linux, PipeWire, kitty for text mode, and the Claude Code CLI logged in).
