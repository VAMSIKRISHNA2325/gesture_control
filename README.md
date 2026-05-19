# Gesture + Voice Control

A hands-free Windows controller using your webcam, hand gestures, and offline voice commands. No internet required after setup.

---

## Quick Start

```bash
pip install mediapipe opencv-python pyautogui vosk sounddevice
python gesture.py
```

Models download automatically on first run (~50 MB for Vosk).

**Failsafe:** move your mouse to the top-left corner of the screen to force-quit.

---

## How It Works

- **Left hand** = mode selector (hold a finger count for 1 second to switch modes)
- **Right hand** = action hand (does the gesture for the current mode)
- **Voice** = always-on, fires regardless of mode. Say `computer <command>`.

---

## Modes

| Left-hand fingers | Mode | What it does |
|---|---|---|
| 0 | IDLE | Nothing. Voice still works. |
| 1 | LAUNCH | Launch apps by finger count |
| 2 | MEDIA | Control music/volume |
| 3 | MOUSE | Full cursor control |
| 4 | WINDOW | Window management |

---

## Mode Gestures

### LAUNCH (left hand: 1 finger)
Hold a finger count on your **right hand** for 0.3s to launch an app.

| Fingers | Default app |
|---|---|
| 1 | Chrome |
| 2 | Notepad |
| 3 | Calculator |

> Edit `gesture_apps.json` to change or add apps (supports up to 4).

---

### MEDIA (left hand: 2 fingers)

| Gesture | Action |
|---|---|
| Swipe right | Next track |
| Swipe left | Previous track |
| Swipe up | Volume up |
| Swipe down | Volume down |
| Pinch | Play / Pause |

---

### MOUSE (left hand: 3 fingers)

| Hand shape | Action |
|---|---|
| **Gun pose** (index up, others curled) | Cursor follows thumb tip |
| Gun pose → pinch | Left click |
| Gun pose → pinch, hold 0.8s still | Right click |
| Gun pose → double pinch at same spot | Double click |
| Gun pose → pinch + move hand | Drag |
| Gun pose → hold still 1s | **Hover lock** — cursor freezes; pinch to unlock |
| Open palm (4 fingers up) | Scroll up |
| Palm flipped (4 fingers down) | Scroll down |

> Run `python calibrate.py` to auto-tune smoothing, deadband, and pinch thresholds to your hand.

---

### WINDOW (left hand: 4 fingers)

| Gesture | Action |
|---|---|
| Swipe left / right | Snap window left / right |
| Swipe up / down | Maximize / Minimize *(only when voice is muted)* |
| Index + middle up → swipe left/right | Switch virtual desktop |
| Pinch (single) | Win+Tab (task view) → aim cursor → pinch again to select |
| Pinch (double, within 0.4s) | Alt+Tab (cycle windows) |
| Fist held 0.5s | Close window (Alt+F4) |

---

## Voice Commands

Say **"computer"** followed by any command below.

| Phrase | Action |
|---|---|
| computer open chrome | Launch Chrome |
| computer open notepad | Launch Notepad |
| computer open calculator | Launch Calculator |
| computer open spotify | Launch Spotify |
| computer open explorer | Launch File Explorer |
| computer play / pause | Play/Pause media |
| computer next / previous | Next/Previous track |
| computer volume up / down | Volume ±5 |
| computer mute / unmute | Toggle mute |
| computer maximize / minimize | Resize active window |
| computer snap left / right | Snap active window |
| computer lock screen | Win+L |
| computer screenshot | Print Screen |
| computer task manager | Ctrl+Shift+Esc |
| computer show desktop | Win+D |
| computer switch window | Alt+Tab |

**Press M** in the camera window to mute/unmute voice without closing the app.

---

## Configuration

### gesture_apps.json
Map finger counts (1–4) to any shell command:
```json
{
  "1": "start chrome",
  "2": "start code",
  "3": "calc.exe",
  "4": "start explorer"
}
```

### config.py
All tunable constants live here with inline comments. Key ones:

| Constant | Default | Effect |
|---|---|---|
| `MOUSE_SMOOTHING` | 0.28 | Cursor lag/smoothness (lower = snappier) |
| `MOUSE_DEADBAND_PX` | 8 | Minimum movement before cursor updates |
| `MOUSE_HOVER_HOLD_SECONDS` | 1.0 | Time to hover before cursor locks |
| `CLICK_PINCH_RATIO_ON` | 0.28 | How tightly to pinch to click |
| `MIC_GAIN` | 30 | Software mic boost (set to 1 if Windows mic is loud enough) |
| `LAUNCH_HOLD_SECONDS` | 0.3 | Hold time to launch an app |

---

## Calibration

Run the calibration tool to auto-tune mouse constants to your specific hand and camera:

```bash
python calibrate.py
```

Three 8-second phases:
1. **STILL** — hold your hand still → sets `MOUSE_DEADBAND_PX`
2. **MOVE** — move naturally → sets `MOUSE_SMOOTHING`
3. **PINCH** — pinch and release repeatedly → sets `CLICK_PINCH_RATIO_ON/OFF`

Press **ENTER** after calibration to write values directly into `config.py`.

---

## Troubleshooting

**Voice not working / mic level shows 0–2:**
The Windows microphone volume is too low. Fix it:
1. `Win+R` → `mmsys.cpl` → Recording tab
2. Double-click your microphone → Levels tab
3. Set volume to **80–100** and Microphone Boost to **+20 dB**
4. Set `MIC_GAIN = 1` in `config.py` once Windows level is fixed.

**Cursor not moving in Mouse mode:**
Make sure your hand is in **gun pose** — index finger pointing up, middle/ring/pinky curled.

**Accidental window snaps in Window mode:**
The snap gesture uses index-only swipes. Virtual desktop uses index+middle. Make sure your middle finger is clearly curled when snapping.

---

## File Structure

```
d:\hands\
├── gesture.py          # Entry point — run this
├── config.py           # All constants and voice commands
├── landmarks.py        # Landmark IDs and pose detection helpers
├── detectors.py        # SwipeDetector, PinchDetector
├── drawing.py          # draw_hand, draw_text, draw_hover_arc
├── voice.py            # VoiceWorker, execute_voice_command
├── calibrate.py        # Mouse auto-calibration tool
├── gesture_apps.json   # App launcher config (edit freely)
├── modes/
│   ├── base.py         # Mode base class
│   ├── idle.py         # IdleMode
│   ├── launch.py       # LaunchMode
│   ├── media.py        # MediaMode
│   ├── mouse.py        # MouseMode ← most complex, ~200 lines
│   └── window.py       # WindowMode
└── README.md           # This file
```

### Where to look when editing

| I want to change... | Edit this file |
|---|---|
| Tuning constants (smoothing, deadband, thresholds) | `config.py` |
| Voice commands | `config.py` → `VOICE_COMMANDS` |
| App shortcuts | `gesture_apps.json` |
| Mouse cursor behaviour | `modes/mouse.py` |
| Window management gestures | `modes/window.py` |
| Media controls | `modes/media.py` |
| App launcher | `modes/launch.py` |
| Hand skeleton drawing | `drawing.py` |
| Pose detection logic | `landmarks.py` |
| Mic boost / audio pipeline | `voice.py` |

---

## Dependencies

```
mediapipe
opencv-python
pyautogui
vosk
sounddevice
numpy   (installed automatically with mediapipe)
```
