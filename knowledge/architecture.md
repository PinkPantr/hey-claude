---
type: concept
title: How hey claude works
description: The end-to-end pipeline — mic capture, wake-word detection, speech-to-text, and the two output paths (live-CLI text injection vs headless spoken reply).
timestamp: 2026-06-18T22:00:00-04:00
status: active
---

# Pipeline

```
mic (parecord, PipeWire)
   │  16kHz mono frames
   ▼
openWakeWord  ── "hey claude"? ──▶  faster-whisper (base.en, CPU int8)   speech → text
   │  no                                     │
   └─ keep listening (nothing leaves box)    ▼
                              ┌──────────────┴──────────────┐
                      text mode │                            │ voice mode
                                ▼                            ▼
                  kitty @ send-text "<text>\r"      claude -p "<text>"
                  → lands in the LIVE Claude          → capture reply
                    Code session, auto-submits        → Piper TTS → speakers
                                                       → "confirm" gate before actions
```

# Components

- **Capture** — `parecord` (PipeWire/PulseAudio) reads the configured mic as 16 kHz mono.
- **Wake word** — `openWakeWord` runs a tiny ONNX classifier every frame. It uses two shared feature
  models (`melspectrogram.onnx`, `embedding_model.onnx`) plus the wake model
  (`models/hey_claude.onnx`). Only after a hit above `wake_threshold` does anything else run. See
  [wake-word.md](wake-word.md).
- **Speech-to-text** — `faster-whisper` (`base.en`, CPU, int8). Guards reject clips shorter than ~0.35s,
  drop segments with high `no_speech_prob`, and flush the mic to avoid transcribing the assistant's own
  TTS echo.
- **Output, text mode** — the transcript is sent to the running terminal via `kitty @ send-text` with a
  trailing carriage return, so it appears in the live Claude Code session and submits. (tmux `send-keys`
  is an alternative backend.) Claude Code has no native "inject" API; terminal send-text is the mechanism.
- **Output, voice mode** — runs headless `claude -p` (cwd defaults to `$HOME`), captures stdout, and
  speaks it with `piper` + the bundled voice in `voices/`. A spoken "confirm" gates state-changing actions.

# Key files

| file | role |
|---|---|
| `claude_voice.py` | the whole daemon; CLI: `start`/`stop`/`status`/`devices`/`test {mic,wake,stt,tts,claude}` |
| `config.json` | mic/sink, mode, wake model + threshold, whisper model, inject target |
| `models/hey_claude.onnx` | trained wake-word classifier |
| `models/oww-features/*.onnx` | shared openWakeWord feature models (installer copies into the venv) |
| `voices/*.onnx` | Piper TTS voice |
| `SKILL.md` | `/claude-voice` skill — interactive launcher (picks mic → output → mode) |

# Runtime controls

Spoken while running: "switch to text" / "switch to voice", "stop listening" / "go to sleep".
The daemon resolves paths from `VOICE_HOME` (set by the launcher to the repo dir), finds `piper` in its
own venv, and auto-locates the `claude` binary.
