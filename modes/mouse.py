"""
modes/mouse.py — Mouse control mode.

Gesture map:
  Gun pose (index up, others curled) → cursor follows thumb tip
  Pinch (quick)                      → left click
  Pinch (hold still 0.8s)            → right click
  Double pinch at same spot          → double click
  Pinch + move >10px                 → drag
  Hold still in dead zone 1s         → hover lock (cursor freezes; pinch to unlock)
  4 fingers up (open palm)           → scroll up
  4 fingers down (palm flipped)      → scroll down

State machine:
  IDLE          → hover tracking → HOVER_LOCKED (only pinch exits)
  CLICK_PENDING → click on release  |  drag if moved  |  right-click if held 0.8s
  DRAGGING      → mouse held; release on pinch-up
"""
import math
from collections import deque

import cv2
import pyautogui

from modes.base import Mode
from config import (SCREEN_W, SCREEN_H,
                    MOUSE_SMOOTHING, MOUSE_MARGIN, MOUSE_DEADBAND_PX,
                    MOUSE_HOVER_DISTANCE_PX, MOUSE_HOVER_HOLD_SECONDS,
                    MOUSE_MOVE_SPEED_PX_PER_SEC,
                    CLICK_LOCK_SECONDS, CLICK_LOOKBACK_SECONDS,
                    CLICK_DRAG_DISTANCE_PX,
                    CLICK_PINCH_RATIO_ON, CLICK_PINCH_RATIO_OFF,
                    RIGHT_CLICK_HOLD_SECONDS,
                    DOUBLE_CLICK_INTERVAL, DOUBLE_CLICK_DISTANCE_PX,
                    SCROLL_TICKS_PER_FIRE, SCROLL_INTERVAL)
from landmarks import (THUMB_TIP, pinch_ratio,
                       count_fingers_up, count_fingers_down, is_cursor_pose)
from detectors import PinchDetector
from drawing import draw_hover_arc


class MouseMode(Mode):
    name  = "MOUSE"
    hint  = "Gun pose=cursor | Pinch=click | Fingers up/down=scroll"
    color = (0, 140, 255)

    def __init__(self):
        self.smoothed          = None
        self.history           = deque(maxlen=12)
        self.pinch             = PinchDetector(ratio_on=CLICK_PINCH_RATIO_ON,
                                               ratio_off=CLICK_PINCH_RATIO_OFF)
        self.mouse_down        = False
        self.locked_pos        = None
        self.lock_until        = 0.0
        self.pinch_start_pos   = None
        self.pinch_start_time  = None
        self.last_target       = None
        self.last_target_time  = None
        self.hover_start_time  = None
        self.hover_anchor      = None
        self.hover_locked      = False
        self.right_click_armed = False
        self.last_click_pos    = None
        self.last_click_time   = 0.0
        self.last_scroll_time  = 0.0
        self.last_moved        = None

    def on_enter(self):
        self.smoothed          = None
        self.history.clear()
        self.pinch.pinched     = False
        if self.mouse_down:
            pyautogui.mouseUp()
        self.mouse_down        = False
        self.locked_pos        = None
        self.pinch_start_pos   = None
        self.pinch_start_time  = None
        self.last_target       = None
        self.last_target_time  = None
        self.hover_start_time  = None
        self.hover_anchor      = None
        self.hover_locked      = False
        self.right_click_armed = False
        self.last_click_pos    = None
        self.last_click_time   = 0.0
        self.last_scroll_time  = 0.0
        self.last_moved        = None

    def on_exit(self):
        if self.mouse_down:
            pyautogui.mouseUp()
            self.mouse_down = False

    def handle(self, right_lm, now, frame):
        if right_lm is None:
            return ""

        # Map thumb tip to screen coordinates
        ix, iy = right_lm[THUMB_TIP].x, right_lm[THUMB_TIP].y
        m  = MOUSE_MARGIN
        nx = max(0.0, min(1.0, (ix - m) / (1 - 2 * m)))
        ny = max(0.0, min(1.0, (iy - m) / (1 - 2 * m)))
        target_x = nx * SCREEN_W
        target_y = ny * SCREEN_H
        self.history.append((target_x, target_y, now))

        # Frame-to-frame movement speed
        if self.last_target is None:
            movement_dist  = 0.0
            movement_speed = 0.0
        else:
            dt             = max(now - self.last_target_time, 1e-6)
            movement_dist  = math.hypot(target_x - self.last_target[0],
                                        target_y - self.last_target[1])
            movement_speed = movement_dist / dt
        self.last_target      = (target_x, target_y)
        self.last_target_time = now

        # Hover lock state machine
        if not self.hover_locked:
            if self.hover_anchor is None:
                if (movement_dist <= MOUSE_HOVER_DISTANCE_PX and
                        movement_speed < MOUSE_MOVE_SPEED_PX_PER_SEC):
                    self.hover_anchor     = (target_x, target_y)
                    self.hover_start_time = now
            else:
                dist_from_anchor = math.hypot(target_x - self.hover_anchor[0],
                                              target_y - self.hover_anchor[1])
                if dist_from_anchor > MOUSE_HOVER_DISTANCE_PX:
                    self.hover_anchor     = None
                    self.hover_start_time = None
                elif now - self.hover_start_time >= MOUSE_HOVER_HOLD_SECONDS:
                    self.hover_locked = True

        # Dead-zone circle + hover arc visual
        cam_x = int(right_lm[THUMB_TIP].x * frame.shape[1])
        cam_y = int(right_lm[THUMB_TIP].y * frame.shape[0])
        if self.hover_anchor is not None:
            cam_r = max(8, int(MOUSE_HOVER_DISTANCE_PX * frame.shape[1] / SCREEN_W))
            cv2.circle(frame, (cam_x, cam_y), cam_r, (80, 180, 80), 1, cv2.LINE_AA)
        if self.hover_locked:
            cv2.circle(frame, (cam_x, cam_y), 22, (0, 255, 180), 2, cv2.LINE_AA)
        elif self.hover_anchor is not None and self.hover_start_time is not None:
            frac = min(1.0, (now - self.hover_start_time) / MOUSE_HOVER_HOLD_SECONDS)
            draw_hover_arc(frame, cam_x, cam_y, frac)

        # Scroll up: open palm (all 4 fingers pointing up)
        if count_fingers_up(right_lm) == 4 and not self.mouse_down:
            if now - self.last_scroll_time > SCROLL_INTERVAL:
                pyautogui.scroll(SCROLL_TICKS_PER_FIRE)
                self.last_scroll_time = now
            return "scroll up"

        # Scroll down: all 4 fingers pointing down (palm flipped)
        if count_fingers_down(right_lm) == 4 and not self.mouse_down:
            if now - self.last_scroll_time > SCROLL_INTERVAL:
                pyautogui.scroll(-SCROLL_TICKS_PER_FIRE)
                self.last_scroll_time = now
            return "scroll down"

        # Cursor/click only active in gun pose
        if not is_cursor_pose(right_lm):
            self.hover_anchor     = None
            self.hover_start_time = None
            return ""

        # Pinch press
        evt = self.pinch.update(pinch_ratio(right_lm))
        if evt == "press":
            was_locked = self.hover_locked
            anchor_pos = self.hover_anchor
            self.hover_locked      = False
            self.hover_start_time  = None
            self.hover_anchor      = None
            self.right_click_armed = False

            if was_locked and anchor_pos is not None:
                pre_pos = anchor_pos
            else:
                pre_pos = (target_x, target_y)
                for hx, hy, ht in reversed(self.history):
                    if now - ht >= CLICK_LOOKBACK_SECONDS:
                        pre_pos = (hx, hy)
                        break
            pyautogui.moveTo(int(pre_pos[0]), int(pre_pos[1]), _pause=False)
            self.pinch_start_pos  = pre_pos
            self.pinch_start_time = now
            self.locked_pos       = pre_pos
            self.lock_until       = now + CLICK_LOCK_SECONDS
            self.smoothed         = pre_pos
            self.last_moved       = pre_pos
            return "pinch ready"

        # Pinch release
        if evt == "release":
            click_pos = self.pinch_start_pos
            result    = ""
            if self.mouse_down:
                pyautogui.mouseUp()
                self.mouse_down = False
                result = "drag release"
            elif click_pos is not None:
                if self.right_click_armed:
                    pyautogui.rightClick(int(click_pos[0]), int(click_pos[1]), _pause=False)
                    result = "right-click"
                    self.right_click_armed = False
                elif (self.last_click_time > 0 and
                      now - self.last_click_time < DOUBLE_CLICK_INTERVAL and
                      self.last_click_pos is not None and
                      math.hypot(click_pos[0] - self.last_click_pos[0],
                                 click_pos[1] - self.last_click_pos[1]) < DOUBLE_CLICK_DISTANCE_PX):
                    pyautogui.doubleClick(int(click_pos[0]), int(click_pos[1]), _pause=False)
                    result = "double-click"
                    self.last_click_time = 0.0
                    self.last_click_pos  = None
                else:
                    pyautogui.click(int(click_pos[0]), int(click_pos[1]), _pause=False)
                    result = "click"
                    self.last_click_time = now
                    self.last_click_pos  = click_pos
            self.locked_pos       = None
            self.pinch_start_pos  = None
            self.pinch_start_time = None
            if click_pos is not None:
                self.hover_anchor     = click_pos
                self.hover_start_time = now
                self.hover_locked     = False
            return result

        # Active pinch — drag / right-click arming / click lock
        if self.pinch_start_pos is not None and not self.mouse_down:
            dx = target_x - self.pinch_start_pos[0]
            dy = target_y - self.pinch_start_pos[1]
            if math.hypot(dx, dy) > CLICK_DRAG_DISTANCE_PX:
                pyautogui.moveTo(int(self.pinch_start_pos[0]),
                                 int(self.pinch_start_pos[1]), _pause=False)
                pyautogui.mouseDown()
                self.mouse_down = True
                self.locked_pos = None
                self.smoothed   = self.pinch_start_pos
                return "drag"
            if (self.pinch_start_time is not None and
                    now - self.pinch_start_time >= RIGHT_CLICK_HOLD_SECONDS and
                    not self.right_click_armed):
                self.right_click_armed = True
            pyautogui.moveTo(int(self.pinch_start_pos[0]),
                             int(self.pinch_start_pos[1]), _pause=False)
            return "right-click armed" if self.right_click_armed else "click locked"

        # Hover lock — cursor frozen until pinch
        if self.hover_locked and not self.mouse_down and self.pinch_start_pos is None:
            if self.hover_anchor is not None:
                pyautogui.moveTo(int(self.hover_anchor[0]),
                                 int(self.hover_anchor[1]), _pause=False)
                self.smoothed = self.hover_anchor
            return "hover locked"

        if self.locked_pos and now >= self.lock_until:
            self.locked_pos = None

        # Normal smoothed cursor movement
        if self.smoothed is None:
            self.smoothed = (target_x, target_y)
        else:
            a = 1 - MOUSE_SMOOTHING
            self.smoothed = (a * target_x + MOUSE_SMOOTHING * self.smoothed[0],
                             a * target_y + MOUSE_SMOOTHING * self.smoothed[1])

        if (self.last_moved is None or
                abs(self.smoothed[0] - self.last_moved[0]) > MOUSE_DEADBAND_PX or
                abs(self.smoothed[1] - self.last_moved[1]) > MOUSE_DEADBAND_PX):
            pyautogui.moveTo(int(self.smoothed[0]), int(self.smoothed[1]), _pause=False)
            self.last_moved = (self.smoothed[0], self.smoothed[1])

        return "drag" if self.mouse_down else ""
