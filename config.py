"""
config.py — All tunable constants, model paths, voice commands, and app mappings.
Edit this file to change behaviour without touching any mode logic.
"""
import json
import os
import urllib.request
import zipfile

import pyautogui

# ---------- SCREEN ----------
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0
SCREEN_W, SCREEN_H = pyautogui.size()

# ---------- MODEL PATHS ----------
HAND_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)
HAND_MODEL_PATH = "hand_landmarker.task"

VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
VOSK_MODEL_DIR = "vosk-model-small-en-us-0.15"
VOSK_MODEL_ZIP = "vosk-model-small-en-us-0.15.zip"


def ensure_hand_model():
    if not os.path.exists(HAND_MODEL_PATH):
        print("Downloading hand model ...")
        urllib.request.urlretrieve(HAND_MODEL_URL, HAND_MODEL_PATH)
        print("Done.")


# ---------- MODE SWITCHING ----------
MODE_SWITCH_HOLD_SECONDS = 1.0   # hold left-hand finger count for this long to switch

# ---------- LAUNCH MODE ----------
LAUNCH_CONFIG_FILE   = "gesture_apps.json"
LAUNCH_HOLD_SECONDS  = 0.3   # hold finger count this long to launch
LAUNCH_COOLDOWN      = 3.0   # seconds before another launch is allowed


def load_gesture_apps():
    defaults = {1: "start chrome", 2: "start notepad", 3: "calc.exe"}
    if os.path.exists(LAUNCH_CONFIG_FILE):
        try:
            with open(LAUNCH_CONFIG_FILE) as f:
                loaded = {int(k): v for k, v in json.load(f).items()}
            print(f"[launch] loaded {len(loaded)} apps from {LAUNCH_CONFIG_FILE}")
            return loaded
        except Exception as e:
            print(f"[launch] config load failed ({e}), using defaults")
    return defaults


GESTURE_TO_APP = load_gesture_apps()

# ---------- MEDIA MODE ----------
PINCH_RATIO_ON  = 0.35   # media pinch activation threshold
PINCH_RATIO_OFF = 0.55   # media pinch release threshold

# ---------- SWIPE DETECTOR ----------
SWIPE_HISTORY_FRAMES        = 12
SWIPE_MIN_DISPLACEMENT      = 0.18   # normalised units (media mode)
SWIPE_MAX_DURATION          = 0.6    # seconds — slower than this is not a swipe
SWIPE_COOLDOWN              = 0.7    # seconds between swipes
WINDOW_SWIPE_MIN_DISPLACEMENT = 0.18 # swipe threshold for window mode

# ---------- WINDOW MODE ----------
WINDOW_POSE_HOLD = 0.5   # seconds to hold fist/palm before action fires

# ---------- MOUSE MODE ----------
MOUSE_SMOOTHING           = 0.28   # exponential smoothing (lower = snappier, higher = smoother)
MOUSE_MARGIN              = 0.15   # screen edge margin (fraction of frame)
MOUSE_DEADBAND_PX         = 8      # minimum cursor movement in pixels
MOUSE_HOVER_DISTANCE_PX   = 28     # dead-zone radius; stay inside to trigger hover lock
MOUSE_HOVER_HOLD_SECONDS  = 1.0    # seconds stationary before cursor locks
MOUSE_MOVE_SPEED_PX_PER_SEC = 300.0

CLICK_LOCK_SECONDS        = 0.25   # cursor freeze after pinch press
CLICK_LOOKBACK_SECONDS    = 0.15   # history lookback to find pre-pinch position
CLICK_DRAG_DISTANCE_PX    = 10     # movement needed to switch pinch → drag
CLICK_PINCH_RATIO_ON      = 0.28   # mouse-mode pinch activation (tighter than media)
CLICK_PINCH_RATIO_OFF     = 0.50   # mouse-mode pinch release

RIGHT_CLICK_HOLD_SECONDS  = 0.8    # hold pinch this long (no move) for right-click
DOUBLE_CLICK_INTERVAL     = 0.4    # max gap between two pinches for double-click
DOUBLE_CLICK_DISTANCE_PX  = 20     # max drift between clicks for double-click

SCROLL_TICKS_PER_FIRE     = 3      # scroll units sent per interval
SCROLL_INTERVAL           = 0.12   # seconds between scroll fires

# ---------- VOICE ----------
VOICE_COOLDOWN = 1.0   # seconds between voice command executions
MIC_GAIN       = 30    # software mic boost (set to 1 if Windows mic level is already high)

VOICE_COMMANDS = {
    # Apps
    "computer open chrome":      ("launch", "start chrome"),
    "computer open notepad":     ("launch", "start notepad"),
    "computer open calculator":  ("launch", "calc.exe"),
    "computer open spotify":     ("launch", "start spotify"),
    "computer open explorer":    ("launch", "explorer"),
    # Media
    "computer play":             ("key", "playpause"),
    "computer pause":            ("key", "playpause"),
    "computer next":             ("key", "nexttrack"),
    "computer next track":       ("key", "nexttrack"),
    "computer previous":         ("key", "prevtrack"),
    "computer back":             ("key", "prevtrack"),
    "computer volume up":        ("key_repeat", "volumeup", 5),
    "computer volume down":      ("key_repeat", "volumedown", 5),
    "computer mute":             ("key", "volumemute"),
    "computer unmute":           ("key", "volumemute"),
    # Windows
    "computer maximize":         ("hotkey", ("winleft", "up")),
    "computer minimize":         ("hotkey", ("winleft", "down")),
    "computer snap left":        ("hotkey", ("winleft", "left")),
    "computer snap right":       ("hotkey", ("winleft", "right")),
    # System
    "computer lock screen":      ("hotkey", ("winleft", "l")),
    "computer screenshot":       ("key", "printscreen"),
    "computer task manager":     ("hotkey", ("ctrl", "shift", "esc")),
    "computer show desktop":     ("hotkey", ("winleft", "d")),
    "computer switch window":    ("hotkey", ("alt", "tab")),
}
