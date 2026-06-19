---
type: project
title: hey claude — what it is
description: A local, hands-free voice assistant that lets you talk to Claude Code in the terminal — say "hey claude", speak, and your words land in the live CLI session or are answered out loud.
timestamp: 2026-06-18T22:00:00-04:00
status: active
---

# What it is

**hey claude** turns a terminal into something you talk to. It listens locally for the wake phrase
**"hey claude"**, transcribes what you say next, and then does one of two things depending on the mode:

- **text mode** (the headline feature): types your transcribed words into the **live Claude Code CLI
  session** and submits them — as if you had typed them yourself. You converse with Claude by voice,
  inside your real session, keeping full context and real permission prompts.
- **voice mode**: runs a separate headless `claude -p`, gets the answer, and **speaks it back** through
  your speakers. Fully hands-free; a spoken **"confirm"** is required before anything that changes state.

# Why it exists

Typing is the bottleneck when working with an AI agent. This makes the interaction conversational and
hands-free without giving up the terminal workflow (the live session, the context, the permission model).

# What's local vs not

Everything in the hot path is **local**: wake-word detection (openWakeWord), speech-to-text
(faster-whisper), and text-to-speech (Piper). Nothing audio leaves the machine. The only external
service is Claude itself, reached through the **Claude Code CLI** the user already has installed.

# Status

Working on Linux. The wake word is a **custom-trained "hey claude"** openWakeWord model (bundled at
`models/hey_claude.onnx`). macOS/Windows support is future work (audio capture + terminal injection
are currently Linux-specific). See [architecture.md](architecture.md) for how the pieces fit and
[install-and-run.md](install-and-run.md) for what you need to run it.
