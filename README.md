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
- **rumps** — macOS menu bar app
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
make test       # run unit tests (no hardware required)
```

---

## Menu bar

Pulse runs as a macOS menu bar app. Click **Pulse** in the menu bar to see:

| Item | Meaning |
|---|---|
| Waiting for Myo… | Dongle connected, armband not yet found |
| Ready | Armband connected, listening for gestures |
| Recording… | Voice capture in progress |
| Transcribing… | Whisper processing audio |
| Retraining model… | Local gesture model is being updated |

The menu also shows your last detected gesture and the last action Pulse performed.

Learning controls are local-only:

| Item | Effect |
|---|---|
| Teach New Gesture… | Save recent EMG samples under a new gesture label |
| Correct Last Gesture… | Relabel the latest EMG window after a bad prediction |
| Retrain Model | Rebuild the personal classifier from `data/raw/` |

---

## Recipe config (`pulse.yaml`)

Drop a `pulse.yaml` at the project root to remap any gesture to any action — no Python required.
Delete it to go back to the default behaviour.

```yaml
profiles:
  default:
    fist: dictate              # toggle voice recording
    wave_out:
      action: key
      keys: [cmd, tab]         # hold Cmd, tap Tab
    wave_in:
      action: key
      keys: [cmd, shift, tab]
    fingers_spread:
      action: key
      keys: [ctrl, up]         # Mission Control

  # App-specific overrides (macOS process name)
  Xcode:
    fist:
      action: key
      keys: [cmd, b]           # Build instead of dictate

sequences:
  # Chain of gestures fired within 1.2 s
  - gestures: [fist, wave_out]
    action:
      action: shell
      command: "open -a 'Claude'"
```

### Action types

| Type | Fields | Effect |
|---|---|---|
| `dictate` | — | Toggle voice recording (FIST default) |
| `key` | `keys: [...]` | Hold modifiers, tap last key |
| `type` | `text: "..."` | Type literal text at cursor |
| `shell` | `command: "..."` | Run shell command in background |

See `pulse.yaml.example` for a fully annotated reference config.

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

You can also teach or correct gestures from the menu bar. Hold the gesture, choose **Teach New Gesture…**, name it, then choose **Retrain Model**. For best adaptive learning, start with `make collect && make train`, then run Pulse with `make custom`. In custom mode, the model reloads after retraining. If you started with `make run`, restart with `make custom` after retraining.

Custom gestures that aren't in the default vocabulary are emitted with `metadata["custom_label"]`, and recipe mode can bind them directly:

```yaml
profiles:
  default:
    pinch:
      action: key
      keys: [cmd, b]
```

All learning data stays local in `data/raw/`, and trained models stay local in `models/`.

---

## Architecture

```
MYO Hardware
    ↓
myo_reader.py       — gesture detection (hardware or custom EMG classifier)
    ↓
Dispatcher          — routes GestureEvents to registered handlers
    ↓
┌─────────────────────────────────────────┐
│ handlers/logger.py                      │  logs every event
│ handlers/recipe_handler.py  (if yaml)   │  gesture → action from pulse.yaml
│   └── frontmost_app.py                  │  macOS app detection for profiles
│ handlers/voice_trigger.py   (default)   │  FIST → record → Whisper → type
│ handlers/window_navigator.py (default)  │  WAVE → Cmd+Tab
└─────────────────────────────────────────┘
    ↓
engine.py           — owns all hardware/audio; exposes state + action callbacks
    ↓
menu_bar.py         — macOS menu bar UI (rumps); reflects live state
```

Adding a new gesture action is one line: `dispatcher.register(your_handler)`.

---

## Project structure

```
PulseCLI/
├── main.py                         entry point
├── pulse.yaml.example              annotated recipe config reference
├── pulse/
│   ├── engine.py                   hardware/audio owner; UI-facing API
│   ├── menu_bar.py                 macOS menu bar app
│   ├── myo_reader.py               MYO connection + gesture pipeline
│   ├── dispatcher.py               event routing
│   ├── events.py                   GestureEvent dataclass
│   ├── gestures.py                 Gesture enum
│   ├── config.py                   pulse.yaml parser + dataclasses
│   ├── frontmost_app.py            macOS frontmost app detection
│   ├── learning.py                 local adaptive gesture sample saving
│   ├── training.py                 reusable Random Forest training
│   ├── voice_recorder.py           mic capture + Whisper transcription
│   ├── emg/
│   │   └── features.py             EMG signal feature extraction
│   └── handlers/
│       ├── recipe_handler.py       YAML-driven gesture → action dispatch
│       ├── voice_trigger.py        voice recording + typing
│       ├── window_navigator.py     app switching
│       └── logger.py               event logging
├── scripts/
│   ├── collect.py                  EMG training data collection
│   └── train.py                    gesture classifier training
└── tests/
    ├── test_config.py              config parser tests
    ├── test_learning.py            local learning tests
    └── test_recipe.py              recipe handler tests
```

---

Built by [@behzad-janjua](https://github.com/behzad-janjua)
