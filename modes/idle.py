"""
modes/idle.py — Idle mode: no right-hand actions, voice still active.
"""
from modes.base import Mode


class IdleMode(Mode):
    name  = "IDLE"
    hint  = "Left-hand finger count (1-4) picks a mode. Voice still works."
    color = (120, 120, 120)
