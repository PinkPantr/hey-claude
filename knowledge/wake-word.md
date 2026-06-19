---
type: concept
title: The "hey claude" wake word
description: How wake detection works, the bundled custom model, and how to change or retrain it.
timestamp: 2026-06-18T22:00:00-04:00
status: active
---

# How wake detection works

A tiny [openWakeWord](https://github.com/dscripka/openWakeWord) ONNX classifier runs on every audio
frame and answers one question — "did I just hear the wake phrase?" — many times per second, entirely
locally. It is not speech recognition; it only recognizes one acoustic pattern. Nothing is transcribed
or sent anywhere until it fires above `wake_threshold`. It relies on two shared feature models
(`melspectrogram.onnx` + `embedding_model.onnx`) plus the wake model itself.

# The bundled model

`models/hey_claude.onnx` is a **custom-trained** classifier for the phrase **"hey claude"**, with
negative examples to suppress near-misses (hey cloud, hey claudia, okay claude, etc.). It is selected by
`config.json` → `"wake_model": "hey_claude.onnx"`. The `wake_key` (used to read the detection score) is
the filename stem, `hey_claude`.

# Changing the wake word

- To use a different **built-in** word, set `wake_model` to e.g. `hey_jarvis`, `alexa`, or `hey_mycroft`
  (openWakeWord ships these; no file needed).
- To use a different **custom** model, drop its `.onnx` in `models/` and point `wake_model` at the
  filename. The shared feature models are already installed, so it just works.

# Retraining (advanced, not in this repo)

The wake model was trained on a GPU using openWakeWord's pipeline (synthetic clips via Piper TTS →
augmentation → a small DNN → ONNX export). That build process is intentionally **not shipped here** —
this repo is the finished product. If you need to retrain (different phrase, more data), use the
upstream [openwakeword-trainer](https://github.com/lgpearson1771/openwakeword-trainer); note the current
Kaggle image (Python 3.12 / torch 2.10) needs several dependency fixes (piper-phonemize-cross,
openwakeword 0.6.0, piper-sample-generator v2.0.0, a torch.load/torchaudio.load shim, and a T4 GPU).
Drop the resulting `hey_claude.onnx` into `models/`.
