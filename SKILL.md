---
name: claude-voice
description: Turn on hands-free voice control of Claude. Run when the user types /claude-voice or says "turn on voice", "let me talk to you", "enable voice mode", "start the voice assistant". Interactively picks the mic + output, asks text (inject into this live chat) or voice (spoken replies), then launches the always-listening daemon.
---

# /claude-voice — launch the voice assistant

Turns on the local "hey jarvis / hey claude" voice listener (`~/claude-voice/`). Follow these steps exactly.

## 0. Handle stop/off
If the user's args contain `stop`, `off`, or `quit`: run `claude-voice stop` and report. Done.

## 1. Preconditions
Run: `claude-voice status` (binary is `~/.local/bin/claude-voice`).
- If the command is missing, tell the user to run the repo's `install.sh` first and stop.
- If it shows **RUNNING**, ask the user whether to **reconfigure** (stop + relaunch) or **leave it**. If leave, stop here.

## 2. Enumerate devices
Run: `claude-voice devices` → JSON with `inputs`, `outputs`, `default_source`, `default_sink`.

## 3. Ask the user (use AskUserQuestion)
Ask up to three questions in one call:
1. **Mic** — options from `inputs[].name` (label them readably; mark the one matching `default_source` as the default — that's the user's current system mic). Prefer a dedicated/USB mic over a webcam mic if both are present.
2. **Output mode** — **Text (reply in this live chat)** vs **Voice (spoken replies)**. Explain: text injects your speech into *this* conversation and I answer here with full context + normal permission prompts; voice uses a headless Claude + spoken reply and is gated by a spoken "confirm" before any action.
3. **Speaker** — ONLY if they chose Voice. Options from `outputs[].name` (default = `default_sink`).

## 4. If mode = text → resolve the live-inject target
**The CURRENT terminal is authoritative.** `KITTY_LISTEN_ON` / `TMUX_PANE` can be **stale** — they're *inherited* when one terminal is launched from inside another (e.g. opening WezTerm from a kitty shell), so `KITTY_LISTEN_ON` being set does **not** mean you're in kitty. Use `TERM_PROGRAM`/`TERM` to decide which terminal you're *actually* in, and ignore env vars belonging to a different one.
```
echo "TERM_PROGRAM=$TERM_PROGRAM ; TERM=$TERM ; WEZTERM_PANE=$WEZTERM_PANE ; KITTY_LISTEN_ON=$KITTY_LISTEN_ON ; KITTY_WINDOW_ID=$KITTY_WINDOW_ID ; TMUX_PANE=$TMUX_PANE"
```
Pick the backend for the terminal you're actually in, in this order:
- **WezTerm (preferred — the only cross-platform option; works on Windows too):** if `TERM_PROGRAM` = `WezTerm` **or** `WEZTERM_PANE` is set → `--inject wezterm --wezterm-pane "$WEZTERM_PANE"`. `$WEZTERM_PANE` is this session's own pane (the inject target). **Ignore any KITTY_*/TMUX_* here — they're stale-inherited.** If unsure, confirm with `wezterm cli list`. (Remote control is on by default.)
- **kitty:** else if `TERM` = `xterm-kitty` **and** `KITTY_LISTEN_ON` is set → `--inject kitty --kitty-listen "$KITTY_LISTEN_ON" --kitty-window "$KITTY_WINDOW_ID"`.
  If `TERM` is kitty but `KITTY_LISTEN_ON` is **empty**, remote control isn't active: confirm `~/.config/kitty/kitty.conf` has `allow_remote_control socket-only` + `listen_on unix:/tmp/kitty`, then tell the user to **fully restart kitty once** and re-run. Stop — do not launch.
- **tmux:** else if `TMUX_PANE` is set → `--inject tmux --tmux-pane "$TMUX_PANE"`.
- **none:** tell the user text mode needs WezTerm (recommended), kitty (remote control on), or tmux; offer Voice mode instead. Stop.

## 5. Launch the daemon (detached so it survives this session)
Build the command from the answers, e.g.:
```
setsid claude-voice start \
  --mode <text|voice> \
  --input "<chosen mic name>" \
  [--output "<chosen sink name>"]  \
  [--inject wezterm --wezterm-pane "$WEZTERM_PANE"   # OR: --inject kitty --kitty-listen "$KITTY_LISTEN_ON" --kitty-window "$KITTY_WINDOW_ID"   # OR: --inject tmux --tmux-pane "$TMUX_PANE"] \
  > ~/claude-voice/daemon.log 2>&1 < /dev/null &
```
Then wait ~3s and run `claude-voice status` + `tail -n 5 ~/claude-voice/daemon.log` to confirm it reached "listening".

## 6. Confirm to the user
Tell them, concisely:
- It's listening; the wake word is **"hey jarvis"** (until the custom `hey_claude.onnx` is installed in `~/claude-voice/models/`).
- **text mode:** say *"hey jarvis, <request>"* and it appears here and submits itself — no Enter.
- **voice mode:** say *"hey jarvis, <question>"* for a spoken answer; actions require you to say **"confirm"**.
- To stop: `/claude-voice stop`, or say **"stop listening"**.

## Notes
- All logic lives in the `claude-voice` CLI (`devices`/`start`/`stop`/`status`) — this skill only drives the questions, so it stays portable for anyone who installs the repo.
- Config is saved to `~/claude-voice/config.json`; next run defaults to the last choice.
