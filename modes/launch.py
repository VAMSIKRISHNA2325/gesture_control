"""
modes/launch.py — Launch mode: hold a finger count to open an app.
Apps are configured in gesture_apps.json (or config.py defaults).
"""
import subprocess

import pyautogui

from modes.base import Mode
from config import GESTURE_TO_APP, LAUNCH_HOLD_SECONDS, LAUNCH_COOLDOWN
from landmarks import count_fingers_up


class LaunchMode(Mode):
    name  = "LAUNCH"
    hint  = "Right hand: 1, 2, or 3 fingers (held 0.3s) to launch"
    color = (0, 200, 80)

    def __init__(self):
        self.candidate       = None
        self.candidate_start = 0.0
        self.cooldown_until  = 0.0

    def on_enter(self):
        self.candidate = None

    def handle(self, right_lm, now, frame):
        if now < self.cooldown_until:
            return f"cooldown {self.cooldown_until - now:.1f}s"
        if right_lm is None:
            self.candidate = None
            return ""

        fingers = count_fingers_up(right_lm)
        if fingers in GESTURE_TO_APP:
            if self.candidate == fingers:
                if now - self.candidate_start >= LAUNCH_HOLD_SECONDS:
                    cmd = GESTURE_TO_APP[fingers]
                    try:
                        subprocess.Popen(cmd, shell=True)
                        print(f"[launch] {cmd}")
                    except Exception as e:
                        print(f"[launch failed] {cmd}: {e}")
                    self.cooldown_until = now + LAUNCH_COOLDOWN
                    self.candidate = None
                    return f"launched: {cmd}"
            else:
                self.candidate       = fingers
                self.candidate_start = now
            return f"holding {fingers}"
        else:
            self.candidate = None
        return ""
