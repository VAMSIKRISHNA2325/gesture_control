"""
modes/__init__.py — Convenience re-export of all mode classes.
"""
from modes.base   import Mode
from modes.idle   import IdleMode
from modes.launch import LaunchMode
from modes.media  import MediaMode
from modes.mouse  import MouseMode
from modes.window import WindowMode

__all__ = ["Mode", "IdleMode", "LaunchMode", "MediaMode", "MouseMode", "WindowMode"]
