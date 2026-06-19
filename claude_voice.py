#!/usr/bin/env python3
"""
claude-voice — hands-free voice control for the Claude CLI.

Two output modes (chosen at launch, usually via the /claude-voice skill):
  • text  : transcribed speech is INJECTED into your live Claude terminal window
            (kitty `@ send-text` or tmux `send-keys`) and auto-submits — you read
            the reply in the real conversation, full context, real permission prompts.
  • voice : transcribed speech goes to a headless `claude -p` and the reply is
            spoken back via Piper TTS. Self-contained, hands-free, no terminal needed.
            Protected by a spoken-"confirm" gate before any state-changing action.

Pipeline: parecord (PipeWire) → openWakeWord → faster-whisper → (inject | claude -p).
All local. Config lives in ~/claude-voice/config.json.

Commands:
  claude-voice devices                 # list mics + speakers as JSON
  claude-voice start [opts]            # write config + run the listener
  claude-voice stop | status
  claude-voice test {mic,wake,stt,tts,claude} [text...]
  claude-voice                         # = start with existing config
"""
import argparse
import fcntl
import glob
import json
import os
import re
import signal
import subprocess
import sys
import time
import wave
from collections import deque

import numpy as np

# ---------------------------------------------------------------- paths (portable)
HOME = os.path.expanduser("~")
PROJECT = os.environ.get("VOICE_HOME", os.path.join(HOME, "claude-voice"))
CONFIG_PATH = os.path.join(PROJECT, "config.json")
PIDFILE = os.path.join(PROJECT, "daemon.pid")
VOICES_DIR = os.path.join(PROJECT, "voices")
MODELS_DIR = os.path.join(PROJECT, "models")
ACK_WAV = os.path.join(PROJECT, "ack.wav")
# piper ships in the same venv as this interpreter — derive, don't hardcode
PIPER_BIN = os.path.join(os.path.dirname(sys.executable), "piper")
CLAUDE_BIN = os.environ.get("VOICE_CLAUDE_BIN") or (
    os.path.join(HOME, ".local/bin/claude") if os.path.exists(os.path.join(HOME, ".local/bin/claude")) else "claude"
)

# ---------------------------------------------------------------- audio constants
SAMPLE_RATE = 16000
FRAME = 1280                      # 80ms @ 16kHz — openWakeWord's chunk
FRAME_BYTES = FRAME * 2
WAKE_COOLDOWN = 2.0
VAD_RMS = int(os.environ.get("VOICE_VAD_RMS", "450"))
VAD_SILENCE = 0.8
VAD_MAX = 12.0
VAD_PREROLL = 0.3
MIN_SPEECH = 0.35

DEFAULT_CONFIG = {
    "input_source": "",          # "" = system default mic
    "output_sink": "",           # "" = default sink (TTS playback)
    "mode": "voice",             # "voice" | "text"
    "wake_model": "hey_jarvis",  # bundled name, or a path to a custom .onnx
    "wake_threshold": 0.5,
    "whisper_model": "base.en",
    "claude_cwd": HOME,          # cwd for headless claude (voice mode)
    "claude_perm": "default",    # safe default; set "bypassPermissions" to let voice mode act autonomously
    "inject": {                  # text mode target
        "backend": "",           # "kitty" | "tmux"
        "kitty_listen_on": "",
        "kitty_window_id": "",
        "tmux_pane": "",
    },
}

# ---------------------------------------------------------------- config
def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    if os.path.exists(CONFIG_PATH):
        try:
            saved = json.load(open(CONFIG_PATH))
            for k, v in saved.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
        except Exception as e:
            log("config load error, using defaults:", e)
    return cfg

def save_config(cfg):
    os.makedirs(PROJECT, exist_ok=True)
    json.dump(cfg, open(CONFIG_PATH, "w"), indent=2)

# ---------------------------------------------------------------- helpers
def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)

def notify(title, body):
    try:
        subprocess.run(["notify-send", "-a", "Claude", title, body], check=False)
    except FileNotFoundError:
        pass

def rms(pcm):
    return float(np.sqrt(np.mean(pcm.astype(np.float32) ** 2))) if pcm.size else 0.0

def save_wav(path, pcm):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())

def open_mic(cfg):
    cmd = ["parecord", "--raw", "--format=s16le", f"--rate={SAMPLE_RATE}", "--channels=1"]
    if cfg.get("input_source"):
        cmd += ["-d", cfg["input_source"]]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

def read_frame(proc):
    fd = proc.stdout.fileno()
    buf = b""
    while len(buf) < FRAME_BYTES:
        try:
            chunk = os.read(fd, FRAME_BYTES - len(buf))
        except BlockingIOError:
            return np.zeros(0, dtype=np.int16)
        if not chunk:
            return np.zeros(0, dtype=np.int16)
        buf += chunk
    return np.frombuffer(buf, dtype=np.int16)

def flush_mic(proc):
    """Drop buffered audio (e.g. TTS echo) so the next capture starts clean."""
    fd = proc.stdout.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    try:
        while True:
            try:
                if not os.read(fd, 65536):
                    break
            except (BlockingIOError, OSError):
                break
    finally:
        fcntl.fcntl(fd, fcntl.F_SETFL, fl)

# ---------------------------------------------------------------- VAD capture
def record_utterance(proc, preroll_frames):
    frames = list(preroll_frames)
    started = False; silence = 0.0; elapsed = 0.0; speech_frames = 0
    per = FRAME / SAMPLE_RATE
    while elapsed < VAD_MAX:
        f = read_frame(proc)
        if f.size == 0:
            break
        frames.append(f); elapsed += per
        if rms(f) >= VAD_RMS:
            started = True; silence = 0.0; speech_frames += 1
        elif started:
            silence += per
            if silence >= VAD_SILENCE:
                break
    audio = np.concatenate(frames) if frames else np.zeros(0, dtype=np.int16)
    return audio, speech_frames * per

def confirm_capture(proc):
    flush_mic(proc)  # drop the spoken-gate echo before listening for "confirm"
    utt, sp = record_utterance(proc, deque())
    return "" if sp < MIN_SPEECH else strip_wake(transcribe(utt))

# ---------------------------------------------------------------- STT
_whisper = None
def transcribe(pcm, model_name="base.en"):
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        log("loading whisper", model_name, "…")
        _whisper = WhisperModel(model_name, device="cpu", compute_type="int8")
    audio = pcm.astype(np.float32) / 32768.0
    segs, _ = _whisper.transcribe(audio, language="en", vad_filter=True,
                                  condition_on_previous_text=False, no_speech_threshold=0.5)
    return " ".join(s.text for s in segs if getattr(s, "no_speech_prob", 0.0) < 0.6).strip()

def strip_wake(text):
    return re.sub(r"^\s*(hey\s+)?(jarvis|claude)[\s,!.?-]*", "", text, flags=re.I).strip()

# ---------------------------------------------------------------- TTS
def piper_voice_path():
    hits = glob.glob(os.path.join(VOICES_DIR, "*.onnx"))
    return hits[0] if hits else None

def _paplay(cfg, wav):
    cmd = ["paplay"]
    if cfg.get("output_sink"):
        cmd += ["-d", cfg["output_sink"]]
    cmd.append(wav)
    subprocess.run(cmd, check=False)

def ack(cfg):
    if not os.path.exists(ACK_WAV):
        t = np.linspace(0, 0.12, int(SAMPLE_RATE * 0.12), endpoint=False)
        save_wav(ACK_WAV, (0.3 * np.sin(2 * np.pi * 880 * t) * 32767).astype(np.int16))
    _paplay(cfg, ACK_WAV)

def speak(cfg, text):
    voice = piper_voice_path()
    if not voice or not os.path.exists(PIPER_BIN):
        log("(tts unavailable — voice model or piper missing)"); return
    out = os.path.join(PROJECT, "reply.wav")
    p = subprocess.run([PIPER_BIN, "-m", voice, "-f", out], input=text.encode(), stderr=subprocess.DEVNULL)
    if p.returncode == 0 and os.path.exists(out):
        _paplay(cfg, out)

# ---------------------------------------------------------------- intent gate (voice mode)
ACTION_RE = re.compile(
    r"\b(delete|remove|rm|erase|wipe|drop|truncate|create|make|build|add|write|edit|"
    r"modify|change|update|rename|move|mv|copy|install|uninstall|run|execute|launch|"
    r"open|play|deploy|commit|push|merge|pull|send|email|post|publish|set|setup|"
    r"configure|enable|disable|turn|start|stop|restart|reboot|kill|fix|refactor|"
    r"generate|download|upload|save|append|replace|clear|reset|format|chmod|schedule)\b", re.I)
QUESTION_RE = re.compile(
    r"^(what|who|whose|whom|when|where|why|which|how|is|are|was|were|do|does|did|can|"
    r"could|will|would|should|tell me|show me|list|read|find|search|look up|explain|"
    r"describe|summarize|define|give me|whats|what's)\b", re.I)
CONFIRM_RE = re.compile(r"\b(confirm|confirmed|yes|yeah|yep|yup|go ahead|do it|affirmative|proceed)\b", re.I)

def classify_intent(text):
    t = text.strip()
    if ACTION_RE.search(t):
        return "action"
    if QUESTION_RE.match(t):
        return "question"
    return "action"

READONLY_SYSTEM = (
    "You are in READ-ONLY voice mode. Answer by reading/inspecting only. Do NOT create, "
    "edit, move, or delete files, and do NOT run state-changing commands. If the request "
    "needs changes, say so in one sentence instead of doing it.")

# ---------------------------------------------------------------- brain
def ask_claude(prompt, cfg, system=None):
    log("-> claude:", prompt)
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "text",
           "--permission-mode", cfg.get("claude_perm", "default")]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        r = subprocess.run(cmd, cwd=cfg.get("claude_cwd", HOME), capture_output=True, text=True, timeout=300)
        return (r.stdout or "").strip() or (r.stderr or "").strip() or "(no reply)"
    except subprocess.TimeoutExpired:
        return "That took too long, I gave up."

def inject_text(cfg, text):
    """Type the transcript into the live terminal session + submit (CR)."""
    text = " ".join(text.split())  # collapse newlines/whitespace — one line, one submit
    inj = cfg.get("inject", {})
    backend = inj.get("backend")
    if backend == "kitty":
        base = ["kitty", "@"]
        if inj.get("kitty_listen_on"):
            base += ["--to", inj["kitty_listen_on"]]
        match = ["--match", f"id:{inj.get('kitty_window_id','')}"]
        # Send the text first, then submit with a DISCRETE Enter after it settles.
        # A CR in the same chunk as the text is treated as a literal newline by
        # multi-line inputs (e.g. Claude Code), so it wouldn't auto-submit.
        # "--" ends option parsing so a transcript starting with "-" can't be smuggled as a flag
        subprocess.run(base + ["send-text", *match, "--", text], check=False)
        time.sleep(0.35)
        subprocess.run(base + ["send-text", *match, "--", "\r"], check=False)
    elif backend == "tmux":
        # same idea: text first, then a separate Enter so it submits ("--" guards flag injection)
        subprocess.run(["tmux", "send-keys", "-t", inj.get("tmux_pane", ""), "--", text], check=False)
        time.sleep(0.35)
        subprocess.run(["tmux", "send-keys", "-t", inj.get("tmux_pane", ""), "Enter"], check=False)
    else:
        log("no inject backend configured — cannot deliver to live session")

def deliver(cfg, transcript, reply):
    print("\n" + "=" * 60 + f"\nYOU: {transcript}\nCLAUDE: {reply}\n" + "=" * 60)
    notify(f"You: {transcript[:40]}", reply[:240])
    speak(cfg, reply)

def handle_control(cfg, text):
    t = text.lower()
    if any(p in t for p in ("stop listening", "go to sleep", "stop the assistant")):
        notify("Claude voice", "Stopping.")
        if cfg.get("mode") == "voice":
            speak(cfg, "Goodbye.")
        log("stop command — exiting")
        raise SystemExit(0)
    if "switch to text" in t:
        cfg["mode"] = "text"; save_config(cfg); notify("Claude", "Live/text mode"); log("mode -> text"); return True
    if "switch to voice" in t:
        cfg["mode"] = "voice"; save_config(cfg); notify("Claude", "Voice mode"); speak(cfg, "Voice mode."); log("mode -> voice"); return True
    return False

def respond(cfg, transcript, confirm_listener=None):
    if not transcript:
        log("(empty transcript, ignoring)"); return
    if handle_control(cfg, transcript):
        return
    if cfg.get("mode") == "text":
        log("inject ->", repr(transcript))
        notify("→ Claude (live)", transcript[:100])
        inject_text(cfg, transcript)
        return
    # voice mode: headless + safety gate + spoken reply
    if classify_intent(transcript) == "question":
        deliver(cfg, transcript, ask_claude(transcript, cfg, system=READONLY_SYSTEM))
        return
    log("ACTION gate:", repr(transcript))
    notify("Confirm action?", transcript)
    speak(cfg, f"You said: {transcript}. Say confirm to run it, or anything else to cancel.")
    if confirm_listener is None:
        log("no confirm listener — cancelling"); return
    ans = confirm_listener()
    log("confirm heard:", repr(ans))
    if CONFIRM_RE.search(ans or ""):
        notify("Running", transcript)
        deliver(cfg, transcript, ask_claude(transcript, cfg))
    else:
        log("not confirmed — cancelled"); notify("Cancelled", transcript); speak(cfg, "Cancelled.")

# ---------------------------------------------------------------- wake
def resolve_wake(cfg):
    wm = cfg["wake_model"]
    if wm.endswith(".onnx"):
        return wm if os.path.isabs(wm) else os.path.join(MODELS_DIR, wm)
    return wm

def load_wake(cfg):
    from openwakeword.model import Model
    return Model(wakeword_models=[resolve_wake(cfg)], inference_framework="onnx")

def wake_key(cfg):
    return os.path.basename(cfg["wake_model"]).replace(".onnx", "")

def wake_score(model, frame, key):
    preds = model.predict(frame)
    k = next((kk for kk in preds if key in kk), None)
    return (preds[k] if k else max(preds.values())), preds

# ---------------------------------------------------------------- daemon control
def write_pid():
    os.makedirs(PROJECT, exist_ok=True)
    open(PIDFILE, "w").write(str(os.getpid()))

def running_pid():
    try:
        pid = int(open(PIDFILE).read().strip())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError, FileNotFoundError):
        return None

def cleanup():
    try:
        if running_pid() in (None, os.getpid()):
            os.remove(PIDFILE)
    except FileNotFoundError:
        pass

def cmd_stop():
    pid = running_pid()
    if pid:
        os.kill(pid, signal.SIGTERM); print(f"stopped (pid {pid})")
    else:
        print("not running")

def cmd_status():
    pid = running_pid()
    cfg = load_config()
    print(f"status : {'RUNNING pid ' + str(pid) if pid else 'stopped'}")
    print(f"mode   : {cfg['mode']}")
    print(f"mic    : {cfg.get('input_source') or '(default)'}")
    print(f"wake   : {cfg['wake_model']} @ {cfg['wake_threshold']}")
    if cfg["mode"] == "text":
        print(f"inject : {cfg['inject'].get('backend') or '(none!)'}")

# ---------------------------------------------------------------- devices
def list_audio():
    def parse(kind):
        try:
            out = subprocess.run(["pactl", "list", "short", kind], capture_output=True, text=True).stdout
        except FileNotFoundError:
            return []
        rows = []
        for line in out.splitlines():
            p = line.split("\t")
            if len(p) >= 2 and not p[1].endswith(".monitor"):
                rows.append({"id": p[0], "name": p[1]})
        return rows
    return {"inputs": parse("sources"), "outputs": parse("sinks"),
            "default_source": subprocess.run(["pactl", "get-default-source"], capture_output=True, text=True).stdout.strip(),
            "default_sink": subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True).stdout.strip()}

# ---------------------------------------------------------------- main loop
def run_loop(cfg):
    if running_pid():
        print(f"already running (pid {running_pid()}); run 'claude-voice stop' first"); return
    write_pid()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    log("loading wake model:", cfg["wake_model"])
    model = load_wake(cfg); key = wake_key(cfg)
    transcribe(np.zeros(SAMPLE_RATE, dtype=np.int16), cfg["whisper_model"])  # warm
    log(f"listening | mic={cfg.get('input_source') or 'default'} | mode={cfg['mode']} | wake={cfg['wake_model']}")
    notify("Claude voice", f"Listening ({cfg['mode']} mode). Say the wake word.")
    proc = open_mic(cfg)
    preroll = deque(maxlen=int(VAD_PREROLL * SAMPLE_RATE / FRAME))
    last_wake = 0.0
    try:
        while True:
            f = read_frame(proc)
            if f.size == 0:
                log("mic stream ended; restarting"); proc.kill(); time.sleep(0.5); proc = open_mic(cfg); continue
            preroll.append(f)
            score, _ = wake_score(model, f, key)
            now = time.time()
            if score >= cfg["wake_threshold"] and (now - last_wake) > WAKE_COOLDOWN:
                last_wake = now
                log(f"WAKE ({score:.2f})")
                ack(cfg); notify("Claude", "Yes?"); model.reset(); flush_mic(proc)
                utt, sp = record_utterance(proc, preroll); preroll.clear()
                if sp < MIN_SPEECH:
                    log(f"no command ({sp:.2f}s speech) — ignoring"); last_wake = time.time(); continue
                text = strip_wake(transcribe(utt, cfg["whisper_model"])); log("heard:", repr(text))
                if len(text) < 2 or not any(c.isalpha() for c in text):
                    log("empty/garbage — ignoring")
                else:
                    respond(cfg, text, confirm_listener=lambda: confirm_capture(proc))
                last_wake = time.time()
    except (KeyboardInterrupt, SystemExit):
        log("stopping")
    finally:
        proc.kill(); cleanup()

# ---------------------------------------------------------------- tests
def test_mic(cfg):
    log(f"recording 3s from {cfg.get('input_source') or 'default'} … talk now")
    proc = open_mic(cfg); frames = []
    for _ in range(int(3 * SAMPLE_RATE / FRAME)):
        f = read_frame(proc)
        if f.size: frames.append(f)
    proc.kill()
    pcm = np.concatenate(frames) if frames else np.zeros(0, dtype=np.int16)
    out = os.path.join(PROJECT, "mic_test.wav"); save_wav(out, pcm)
    log(f"level RMS={rms(pcm):.0f} (silence<100, speech>400) — saved {out}")

def test_wake(cfg):
    log("say the wake word; scores >0.1 print. Ctrl-C to stop.")
    model = load_wake(cfg); key = wake_key(cfg); proc = open_mic(cfg)
    try:
        while True:
            f = read_frame(proc)
            if f.size == 0: continue
            score, preds = wake_score(model, f, key)
            if score > 0.1: log(f"score={score:.2f}")
            if score >= cfg["wake_threshold"]:
                log("*** WAKE ***"); model.reset(); time.sleep(1)
    except KeyboardInterrupt:
        proc.kill()

def test_stt(cfg):
    proc = open_mic(cfg)
    utt, sp = record_utterance(proc, deque()); proc.kill()
    log(f"captured {utt.size/SAMPLE_RATE:.1f}s ({sp:.1f}s speech)")
    log("transcript:", repr(strip_wake(transcribe(utt, cfg["whisper_model"]))))

# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(prog="claude-voice")
    sub = ap.add_subparsers(dest="cmd")
    sp = sub.add_parser("start")
    sp.add_argument("--input"); sp.add_argument("--output"); sp.add_argument("--mode", choices=["text", "voice"])
    sp.add_argument("--wake"); sp.add_argument("--threshold", type=float); sp.add_argument("--cwd")
    sp.add_argument("--inject", choices=["kitty", "tmux"])
    sp.add_argument("--kitty-listen"); sp.add_argument("--kitty-window"); sp.add_argument("--tmux-pane")
    sub.add_parser("stop"); sub.add_parser("status"); sub.add_parser("devices")
    tp = sub.add_parser("test"); tp.add_argument("stage", choices=["mic", "wake", "stt", "tts", "claude"])
    tp.add_argument("text", nargs="*")
    args = ap.parse_args()
    cmd = args.cmd or "start"

    if cmd == "devices":
        print(json.dumps(list_audio(), indent=2)); return
    if cmd == "stop":
        cmd_stop(); return
    if cmd == "status":
        cmd_status(); return

    cfg = load_config()
    if cmd == "test":
        if args.stage == "mic": test_mic(cfg)
        elif args.stage == "wake": test_wake(cfg)
        elif args.stage == "stt": test_stt(cfg)
        elif args.stage == "tts": speak(cfg, " ".join(args.text) or "Hello, this is Claude.")
        elif args.stage == "claude": print(ask_claude(" ".join(args.text) or "say hello in five words", cfg))
        return

    # start
    if cmd == "start":
        if args.input is not None: cfg["input_source"] = args.input
        if args.output is not None: cfg["output_sink"] = args.output
        if args.mode: cfg["mode"] = args.mode
        if args.wake: cfg["wake_model"] = args.wake
        if args.threshold: cfg["wake_threshold"] = args.threshold
        if args.cwd: cfg["claude_cwd"] = args.cwd
        if args.inject:
            cfg["inject"]["backend"] = args.inject
            if args.kitty_listen: cfg["inject"]["kitty_listen_on"] = args.kitty_listen
            if args.kitty_window: cfg["inject"]["kitty_window_id"] = args.kitty_window
            if args.tmux_pane: cfg["inject"]["tmux_pane"] = args.tmux_pane
        save_config(cfg)
    run_loop(cfg)

if __name__ == "__main__":
    main()
