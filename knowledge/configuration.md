---
type: concept
title: hey claude configuration
description: Every field in config.json, what it controls, and safe defaults.
timestamp: 2026-06-18T22:00:00-04:00
status: active
---

# config.json

```json
{
  "input_source": "",
  "output_sink": "",
  "mode": "text",
  "wake_model": "hey_claude.onnx",
  "wake_threshold": 0.5,
  "whisper_model": "base.en",
  "claude_perm": "default",
  "inject": { "backend": "kitty", "kitty_listen_on": "", "kitty_window_id": "", "tmux_pane": "" }
}
```

| field | meaning |
|---|---|
| `input_source` | PipeWire/PulseAudio source (mic). Empty = system default. List with `claude-voice devices`. |
| `output_sink` | output sink for spoken replies. Empty = default. |
| `mode` | `text` (inject into live CLI) or `voice` (headless + spoken). Switchable by voice at runtime. |
| `wake_model` | `hey_claude.onnx` (bundled, resolved under `models/`), an absolute `.onnx` path, or a built-in name like `hey_jarvis`. |
| `wake_threshold` | 0–1 detection sensitivity. Lower = more sensitive (more false triggers). 0.5 is a good start. |
| `whisper_model` | faster-whisper model id, default `base.en`. `tiny.en` is faster/smaller, `small.en` more accurate. |
| `claude_perm` | permission mode passed to headless `claude` in voice mode. See the warning below. |
| `inject.backend` | `kitty` (default) or `tmux` for text mode. |
| `inject.kitty_listen_on` / `kitty_window_id` | kitty socket + window; usually auto-filled by the `/claude-voice` skill from the environment. |
| `inject.tmux_pane` | target pane if using the tmux backend. |

# claude_perm — default is safe; bypass is opt-in

Ships as **`default`** (safe): in **voice mode** the headless `claude -p` won't take state-changing
actions without permission, so it's good for asking questions out loud. If you want voice mode to be
fully hands-free and *act* on things, set `claude_perm` to **`bypassPermissions`** — understand that a
spoken request can then take real actions. The built-in **spoken "confirm" gate** is the mitigation, but
treat `bypassPermissions` as a deliberate choice. **text mode** ignores `claude_perm` entirely — it just
types into your live session, keeping your normal interactive permission prompts.

# Notes

- `text` mode does not use `claude_perm` — it just types into your live session, which keeps your
  existing permission settings and context.
- Paths are resolved relative to `VOICE_HOME` (the repo dir, set by the launcher).
