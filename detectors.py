"""
detectors.py — Reusable gesture detector classes used across multiple modes.
"""
from collections import deque
from config import (SWIPE_HISTORY_FRAMES, SWIPE_MIN_DISPLACEMENT,
                    SWIPE_MAX_DURATION, SWIPE_COOLDOWN,
                    PINCH_RATIO_ON, PINCH_RATIO_OFF)


class SwipeDetector:
    """Detects directional swipes from a sequence of (x, y) positions."""

    def __init__(self, min_displacement=None):
        self.history         = deque(maxlen=SWIPE_HISTORY_FRAMES)
        self.last_swipe_time = 0.0
        self.min_displacement = (min_displacement
                                 if min_displacement is not None
                                 else SWIPE_MIN_DISPLACEMENT)

    def reset(self):
        self.history.clear()

    def update_and_detect(self, x, y, now):
        """
        Feed the current wrist position and timestamp.
        Returns "left" | "right" | "up" | "down" | None.
        """
        self.history.append((now, x, y))
        if now - self.last_swipe_time < SWIPE_COOLDOWN:
            return None
        if len(self.history) < 5:
            return None
        t0, x0, y0 = self.history[0]
        t1, x1, y1 = self.history[-1]
        dt = t1 - t0
        if not (0.05 < dt < SWIPE_MAX_DURATION):
            return None
        dx, dy   = x1 - x0, y1 - y0
        adx, ady = abs(dx), abs(dy)
        if adx > self.min_displacement and adx > 1.5 * ady:
            self.last_swipe_time = now
            self.history.clear()
            return "right" if dx > 0 else "left"
        if ady > self.min_displacement and ady > 1.5 * adx:
            self.last_swipe_time = now
            self.history.clear()
            return "down" if dy > 0 else "up"
        return None


class PinchDetector:
    """
    Hysteresis-based pinch state machine.
    Returns "press" when pinch_ratio drops below ratio_on,
    "release" when it rises above ratio_off, None otherwise.
    """

    def __init__(self, ratio_on=None, ratio_off=None):
        self.pinched  = False
        self.ratio_on  = ratio_on  if ratio_on  is not None else PINCH_RATIO_ON
        self.ratio_off = ratio_off if ratio_off is not None else PINCH_RATIO_OFF

    def update(self, ratio):
        if not self.pinched and ratio < self.ratio_on:
            self.pinched = True
            return "press"
        if self.pinched and ratio > self.ratio_off:
            self.pinched = False
            return "release"
        return None
