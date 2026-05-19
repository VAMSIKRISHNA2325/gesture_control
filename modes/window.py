"""
modes/window.py — Window management mode.

Gesture map:
  Swipe L/R                → snap window left/right (Win+Left/Right)
  Swipe U/D                → maximize/minimize (only when voice is muted)
  Index+middle up + swipe  → switch virtual desktop (Win+Ctrl+Left/Right)
  Single pinch             → Win+Tab (task view) then cursor aim mode
  Double pinch             → Alt+Tab (cycle windows)
  Fist held 0.5s           → close window (Alt+F4)

Note: swipe direction is corrected for the mirrored camera feed.
"""
import pyautogui

from modes.base import Mode
from config import (SCREEN_W, SCREEN_H, MOUSE_SMOOTHING, MOUSE_MARGIN,
                    WINDOW_SWIPE_MIN_DISPLACEMENT, WINDOW_POSE_HOLD,
                    CLICK_PINCH_RATIO_ON, CLICK_PINCH_RATIO_OFF,
                    DOUBLE_CLICK_INTERVAL)
from landmarks import (WRIST, THUMB_TIP, count_fingers_up,
                       is_two_fingers, pinch_ratio)
from detectors import SwipeDetector, PinchDetector
from drawing import draw_hover_arc


class WindowMode(Mode):
    name  = "WINDOW"
    hint  = "Swipe=snap | 2-finger=desktop | Pinch=Win+Tab | 2xPinch=Alt+Tab | Fist=close"
    color = (180, 0, 255)

    def __init__(self):
        self.swipe           = SwipeDetector(min_displacement=WINDOW_SWIPE_MIN_DISPLACEMENT)
        self.pinch           = PinchDetector(ratio_on=CLICK_PINCH_RATIO_ON,
                                             ratio_off=CLICK_PINCH_RATIO_OFF)
        self.pose_type       = None
        self.pose_start      = 0.0
        self.pose_cooldown   = 0.0
        self.alt_tab_mode    = False
        self.alt_tab_smooth  = None
        self.last_pinch_time = 0.0
        # voice: set externally in main() so up/down swipes work as fallback when muted
        self.voice           = None

    def on_enter(self):
        self.swipe.reset()
        self.pinch.pinched   = False
        self.pose_type       = None
        self.pose_start      = 0.0
        self.pose_cooldown   = 0.0
        self.alt_tab_mode    = False
        self.alt_tab_smooth  = None
        self.last_pinch_time = 0.0

    def handle(self, right_lm, now, frame):
        if right_lm is None:
            self.swipe.reset()
            self.pose_type    = None
            self.alt_tab_mode = False
            return ""

        wrist        = right_lm[WRIST]
        finger_count = count_fingers_up(right_lm)

        # Win+Tab cursor sub-mode: thumb drives cursor, pinch selects window
        if self.alt_tab_mode:
            ix, iy = right_lm[THUMB_TIP].x, right_lm[THUMB_TIP].y
            m  = MOUSE_MARGIN
            nx = max(0.0, min(1.0, (ix - m) / (1 - 2 * m)))
            ny = max(0.0, min(1.0, (iy - m) / (1 - 2 * m)))
            tx, ty = nx * SCREEN_W, ny * SCREEN_H
            if self.alt_tab_smooth is None:
                self.alt_tab_smooth = (tx, ty)
            else:
                a = 1 - MOUSE_SMOOTHING
                self.alt_tab_smooth = (a * tx + MOUSE_SMOOTHING * self.alt_tab_smooth[0],
                                       a * ty + MOUSE_SMOOTHING * self.alt_tab_smooth[1])
            pyautogui.moveTo(int(self.alt_tab_smooth[0]),
                             int(self.alt_tab_smooth[1]), _pause=False)
            evt = self.pinch.update(pinch_ratio(right_lm))
            if evt == "release":
                pyautogui.click(_pause=False)
                self.alt_tab_mode    = False
                self.alt_tab_smooth  = None
                self.pose_cooldown   = now + 1.0
                return "selected"
            return "aim & pinch to select"

        # Fist hold → close window (Alt+F4)
        if now >= self.pose_cooldown:
            if finger_count == 0:
                if self.pose_type != "fist":
                    self.pose_type  = "fist"
                    self.pose_start = now
                elif now - self.pose_start >= WINDOW_POSE_HOLD:
                    pyautogui.hotkey("alt", "f4")
                    self.pose_cooldown = now + 2.0
                    self.pose_type     = None
                    return "close window"
                frac  = min(1.0, (now - self.pose_start) / WINDOW_POSE_HOLD)
                cam_x = int(wrist.x * frame.shape[1])
                cam_y = int(wrist.y * frame.shape[0])
                draw_hover_arc(frame, cam_x, cam_y, frac, color=(0, 80, 220))
                return f"close {frac*100:.0f}%"
            else:
                self.pose_type = None

        # Pinch: single → Win+Tab + aim; double → Alt+Tab
        evt = self.pinch.update(pinch_ratio(right_lm))
        if evt == "release" and now >= self.pose_cooldown:
            if now - self.last_pinch_time < DOUBLE_CLICK_INTERVAL:
                pyautogui.hotkey("alt", "tab")
                self.last_pinch_time = 0.0
                self.pose_cooldown   = now + 1.0
                return "Alt+Tab"
            else:
                pyautogui.hotkey("winleft", "tab")
                self.alt_tab_mode    = True
                self.alt_tab_smooth  = None
                self.last_pinch_time = now
                return "Win+Tab — aim & pinch"

        # Swipe gestures
        direction = self.swipe.update_and_detect(wrist.x, wrist.y, now)
        if direction:
            if is_two_fingers(right_lm) and direction in ("left", "right"):
                # Mirror-corrected virtual desktop direction
                desk_dir = "left" if direction == "right" else "right"
                pyautogui.hotkey("winleft", "ctrl", desk_dir)
                return f"desktop {desk_dir}"
            elif direction in ("left", "right"):
                pyautogui.hotkey("winleft", direction)
                return f"Win+{direction}"
            elif direction in ("up", "down"):
                # Maximize/minimize only when voice is muted (fallback for voice commands)
                voice_muted = self.voice is not None and self.voice.muted
                if voice_muted:
                    pyautogui.hotkey("winleft", direction)
                    return f"Win+{direction}"

        return ""
