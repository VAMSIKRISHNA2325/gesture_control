"""
landmarks.py — MediaPipe hand landmark indices and pose-detection helpers.
All gesture logic that classifies a hand shape lives here.
"""

# ---------- LANDMARK INDICES (MediaPipe 21-point hand model) ----------
WRIST      = 0
THUMB_TIP  = 4
INDEX_PIP  = 6;  INDEX_TIP  = 8
MIDDLE_MCP = 9;  MIDDLE_PIP = 10; MIDDLE_TIP = 12
RING_PIP   = 14; RING_TIP   = 16
PINKY_PIP  = 18; PINKY_TIP  = 20


# ---------- FINGER STATE HELPERS ----------

def count_fingers_up(landmarks):
    """Count fingers whose tips are above their PIP joints (pointing up)."""
    tip_ids = [INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
    pip_ids = [INDEX_PIP, MIDDLE_PIP, RING_PIP, PINKY_PIP]
    return sum(1 for t, p in zip(tip_ids, pip_ids)
               if landmarks[t].y < landmarks[p].y)


def count_fingers_down(landmarks):
    """Count fingers whose tips are below their PIP joints (pointing down)."""
    tip_ids = [INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
    pip_ids = [INDEX_PIP, MIDDLE_PIP, RING_PIP, PINKY_PIP]
    return sum(1 for t, p in zip(tip_ids, pip_ids)
               if landmarks[t].y > landmarks[p].y)


# ---------- POSE DETECTORS ----------

def is_cursor_pose(landmarks):
    """Index extended, middle/ring/pinky curled — activates mouse cursor and click."""
    return (landmarks[INDEX_TIP].y  < landmarks[INDEX_PIP].y  and
            landmarks[MIDDLE_TIP].y > landmarks[MIDDLE_PIP].y and
            landmarks[RING_TIP].y   > landmarks[RING_PIP].y   and
            landmarks[PINKY_TIP].y  > landmarks[PINKY_PIP].y)


def is_two_fingers(landmarks):
    """Index + middle extended, ring + pinky curled — virtual desktop swipe modifier."""
    return (landmarks[INDEX_TIP].y  < landmarks[INDEX_PIP].y  and
            landmarks[MIDDLE_TIP].y < landmarks[MIDDLE_PIP].y and
            landmarks[RING_TIP].y   > landmarks[RING_PIP].y   and
            landmarks[PINKY_TIP].y  > landmarks[PINKY_PIP].y)


# ---------- MEASUREMENT HELPERS ----------

def palm_size(landmarks):
    """Wrist-to-middle-MCP distance — used to normalise pinch ratio."""
    dx = landmarks[MIDDLE_MCP].x - landmarks[WRIST].x
    dy = landmarks[MIDDLE_MCP].y - landmarks[WRIST].y
    return (dx * dx + dy * dy) ** 0.5


def pinch_ratio(landmarks):
    """Thumb-tip to index-tip distance normalised by palm size. ~0 = pinching, ~0.5 = open."""
    import math
    dx = landmarks[THUMB_TIP].x - landmarks[INDEX_TIP].x
    dy = landmarks[THUMB_TIP].y - landmarks[INDEX_TIP].y
    p  = palm_size(landmarks)
    return math.hypot(dx, dy) / p if p > 1e-6 else 1.0
