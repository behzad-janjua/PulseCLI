# PulseCLI

A wearable gesture + voice interface for AI-assisted software engineering.

Wear a MYO armband. Wave to switch apps. Make a fist to speak. Your voice gets transcribed locally and typed wherever your cursor is — including Claude Code.

No cloud. No subscription. Runs entirely on your machine.

---

## What it does

| Gesture | Action |
|---|---|
| Fist (1st) | Start voice recording |
| Fist (2nd) | Stop, transcribe, type at cursor |
| Wave out | Switch to next app (Cmd+Tab) |
| Wave in | Switch to previous app |
| Fingers spread | Mission Control |

Voice is transcribed locally using [Whisper](https://github.com/openai/whisper). No audio leaves your machine.

---

## Stack

- **MYO armband** — EMG muscle sensor, reads gesture intent from forearm
- **pyomyo** — direct USB dongle communication, no Myo Connect required
- **sounddevice** — mic capture
- **Whisper** — local speech-to-text (base model, ~145MB)
- **pynput** — keyboard simulation for typing and app switching
- **scikit-learn** — personal gesture classifier (optional, trained on your own EMG data)

---

## Setup

```bash
# System dependencies
make deps

# Python environment
make install
```

Requires Python 3.11+, macOS, and the MYO USB Bluetooth dongle.

Grant your terminal **Accessibility** and **Microphone** permissions in System Settings → Privacy & Security.

---

## Usage

```bash
make run        # hardware gesture classifier (default)
make custom     # your personal trained classifier
make discover   # debug mode — prints raw MYO pose values
```

---

## Personal gesture training

The MYO's built-in classifier works out of the box. If you want a classifier trained specifically on your arm:

```bash
make collect              # guided data collection (~10 min)
make train                # trains a Random Forest on your data
make custom               # run with your personal model
```

To add a custom gesture that doesn't exist in the default set:

```bash
make add GESTURE=pinch    # collect data for your new gesture
make train                # retrain
make custom               # your new gesture is now live
```

Custom gestures that aren't in the default vocabulary are emitted with `metadata["custom_label"]` so you can wire them to any action in `pulse/handlers/`.

---

## Architecture

```
MYO Hardware
    ↓
myo_reader.py       — gesture detection (hardware or custom EMG classifier)
    ↓
Dispatcher          — routes GestureEvents to registered handlers
    ↓
┌─────────────────────────────────┐
│ handlers/logger.py              │  logs every event
│ handlers/voice_trigger.py       │  FIST → record → Whisper → type
│ handlers/window_navigator.py    │  WAVE → Cmd+Tab
└─────────────────────────────────┘
```

Adding a new gesture action is one line: `dispatcher.register(your_handler)`.

---

## Project structure

```
PulseCLI/
├── main.py                         entry point
├── pulse/
│   ├── myo_reader.py               MYO connection + gesture pipeline
│   ├── dispatcher.py               event routing
│   ├── events.py                   GestureEvent dataclass
│   ├── gestures.py                 Gesture enum
│   ├── voice_recorder.py           mic capture + Whisper transcription
│   ├── emg/
│   │   └── features.py             EMG signal feature extraction
│   └── handlers/
│       ├── voice_trigger.py        voice recording + typing
│       ├── window_navigator.py     app switching
│       └── logger.py               event logging
└── scripts/
    ├── collect.py                  EMG training data collection
    └── train.py                    gesture classifier training
```

---

Built by [@behzad-janjua](https://github.com/behzad-janjua)
