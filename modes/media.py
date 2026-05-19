"""
modes/media.py — Media control mode.
Swipe L/R = previous/next track.
Swipe U/D = volume down/up.
Pinch     = play/pause.
"""
import pyautogui

from modes.base import Mode
from config import PINCH_RATIO_ON, PINCH_RATIO_OFF
from landmarks import WRIST, pinch_ratio
from detectors import SwipeDetector, PinchDetector


class MediaMode(Mode):
    name  = "MEDIA"
    hint  = "Swipe L/R=track | Swipe U/D=volume | Pinch=play/pause"
    color = (255, 140, 0)

    def __init__(self):
        self.swipe = SwipeDetector()
        self.pinch = PinchDetector(ratio_on=PINCH_RATIO_ON, ratio_off=PINCH_RATIO_OFF)

    def on_enter(self):
        self.swipe.reset()
        self.pinch.pinched = False

    def handle(self, right_lm, now, frame):
        if right_lm is None:
            self.swipe.reset()
            return ""

        wrist     = right_lm[WRIST]
        direction = self.swipe.update_and_detect(wrist.x, wrist.y, now)
        if direction:
            key_map = {"right": "nexttrack", "left": "prevtrack",
                       "up": "volumeup",   "down": "volumedown"}
            key     = key_map[direction]
            repeats = 3 if direction in ("up", "down") else 1
            for _ in range(repeats):
                pyautogui.press(key)
            return f"{direction} → {key}"

        evt = self.pinch.update(pinch_ratio(right_lm))
        if evt == "press":
            pyautogui.press("playpause")
            return "play/pause"
        return ""
