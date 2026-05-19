"""
modes/base.py — Abstract base class that every mode inherits from.
"""


class Mode:
    name  = "BASE"
    hint  = ""
    color = (120, 120, 120)   # BGR accent colour used in the HUD

    def on_enter(self):
        """Called when this mode becomes active."""

    def on_exit(self):
        """Called when leaving this mode (clean up OS state, e.g. mouseUp)."""

    def handle(self, right_lm, now, frame):
        """
        Called every frame while this mode is active.
        right_lm : list of 21 MediaPipe landmarks for the action hand, or None.
        now      : current time.time() timestamp.
        frame    : the BGR OpenCV frame (may be drawn on for visual feedback).
        Returns  : short status string shown in the HUD, or "".
        """
        return ""
