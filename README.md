# PulseCLI

Control your entire dev environment with your arm.

Wear a MYO armband. Flex to speak. Wave to switch windows. Route voice prompts to specific Claude sessions — with full git context attached — without touching your keyboard.

No cloud. No subscription. Everything runs on your machine.

---

## Gestures

| Gesture | Default action |
|---|---|
| Fist × 1 | Start voice recording |
| Fist × 2 | Stop, transcribe, type at cursor |
| Wave out | Next app (Cmd+Tab) |
| Wave in | Previous app |
| Fingers spread | Mission Control |

All gestures are remappable. Any gesture can trigger any action — keystrokes, shell commands, window focus, or AI prompts with context.

---

## Two-Claude Command Center

The built-in prompt context system lets you route prompts to named windows with cwd, branch, and git state automatically appended.

```yaml
profiles:
  default:
    wave_in:
      action: focus_target
      target: claude_left

    wave_out:
      action: focus_target
      target: claude_right

    fingers_spread:
      action: context_type
      text: "Review this"

    thumb_to_pinky:
      action: context_type
      text: "Write tests"
```

When `fingers_spread` fires, the prompt lands in the focused Claude session looking like this:

```
Review this

Context:
- app: Terminal
- cwd: PulseCLI
- branch: feature/prompt-context
- uncommitted changes: yes
```

Save targets from the menu bar or via a `save_target` gesture. Targets persist across restarts in `.pulse_targets.yaml`.

---

## Stack

- **MYO armband** — EMG muscle sensor, reads gesture intent from forearm
- **pyomyo** — direct USB dongle communication, no Myo Connect required
- **Whisper** — local speech-to-text (base model, ~145MB, never leaves your machine)
- **pynput** — keyboard simulation
- **rumps** — macOS menu bar
- **scikit-learn** — personal gesture classifier trained on your own EMG data

---

## Setup

```bash
make deps      # install portaudio + ffmpeg via Homebrew
make install   # create .venv and install Python packages
```

Requires Python 3.11+, macOS, and the MYO USB Bluetooth dongle.

Grant your terminal **Accessibility** and **Microphone** permissions in System Settings → Privacy & Security.

---

## Run

```bash
make run        # default hardware gesture classifier
make custom     # your personal trained classifier
make discover   # debug mode — prints raw MYO pose values
make test       # run tests (no hardware required)
```

---

## Recipe config (`pulse.yaml`)

Drop a `pulse.yaml` at the project root to remap gestures. Delete it to restore defaults.

### Action types

| Type | Fields | Effect |
|---|---|---|
| `dictate` | — | Toggle voice recording |
| `key` | `keys: [...]` | Hold modifiers, tap last key |
| `type` | `text: "..."` | Type literal text at cursor |
| `shell` | `command: "..."` | Run shell command in background |
| `context_type` | `text`, `target?` | Type text + cwd/branch/app context block |
| `context_dictate` | `target?` | Dictate + context block appended on transcription |
| `save_target` | `target` | Save frontmost window under a name |
| `focus_target` | `target` | Raise a saved window |
| `next_target` | — | Cycle forward through saved windows |
| `previous_target` | — | Cycle backward through saved windows |

Gestures can be chained into sequences:

```yaml
sequences:
  - gestures: [fist, wave_out]
    action:
      action: shell
      command: "open -a 'Claude'"
```

Sequences take priority over single-gesture bindings and must complete within 1.2 s.

See `pulse.yaml.example` for a fully annotated reference.

---

## Personal gesture training

The MYO's built-in classifier works out of the box. To train one on your arm:

```bash
make collect              # guided data collection (~10 min)
make train                # trains a Random Forest on your data
make custom               # run with your personal model
```

Add a gesture that doesn't exist in the default set:

```bash
make add GESTURE=pinch
make train
make custom
```

You can also teach and correct gestures live from the menu bar — no restart required.

Custom gestures emit `metadata["custom_label"]` and bind directly in `pulse.yaml`:

```yaml
profiles:
  default:
    pinch:
      action: key
      keys: [cmd, b]
```

All training data stays local in `data/raw/`. Models stay local in `models/`.

---

## Architecture

```
MYO Hardware
    ↓
myo_reader.py        gesture detection (hardware or custom EMG classifier)
    ↓
Dispatcher           routes GestureEvents to registered handlers
    ↓
┌──────────────────────────────────────────────┐
│ handlers/recipe_handler.py   (if yaml)       │  gesture → action from pulse.yaml
│   ├── prompt_context.py                      │  cwd/branch/app context builder
│   ├── window_targets.py                      │  named window save/focus/cycle
│   └── frontmost_app.py                       │  macOS app detection for profiles
│ handlers/voice_trigger.py    (default)       │  fist → record → Whisper → type
│ handlers/window_navigator.py (default)       │  wave → Cmd+Tab
│ handlers/logger.py                           │  logs every event
└──────────────────────────────────────────────┘
    ↓
engine.py            owns hardware/audio; exposes state + action callbacks
    ↓
menu_bar.py          macOS menu bar UI; reflects live state, manages targets
```

---

## Project structure

```
PulseCLI/
├── main.py
├── pulse.yaml                      your active recipe config
├── pulse.yaml.example              annotated reference
├── pulse/
│   ├── engine.py
│   ├── menu_bar.py
│   ├── myo_reader.py
│   ├── dispatcher.py
│   ├── config.py
│   ├── prompt_context.py           cwd/branch/app context for AI prompts
│   ├── window_targets.py           named window save/focus/cycle/delete
│   ├── target_picker.py            floating window picker overlay
│   ├── voice_recorder.py
│   ├── learning.py
│   ├── training.py
│   ├── frontmost_app.py
│   ├── emg/
│   │   └── features.py
│   └── handlers/
│       ├── recipe_handler.py
│       ├── voice_trigger.py
│       ├── window_navigator.py
│       └── logger.py
├── scripts/
│   ├── collect.py
│   └── train.py
└── tests/
```

---

Built by [@behzad-janjua](https://github.com/behzad-janjua)
