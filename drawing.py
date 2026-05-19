"""
drawing.py — OpenCV drawing helpers for the HUD and hand skeleton overlay.
"""
import cv2

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]


def draw_hand(frame, landmarks, color_line=(255, 255, 255), color_pt=(0, 0, 255)):
    """Draw the full hand skeleton onto frame."""
    h, w = frame.shape[:2]
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, pts[a], pts[b], color_line, 2)
    for x, y in pts:
        cv2.circle(frame, (x, y), 4, color_pt, -1)


def draw_text(frame, text, pos, size=0.5, thickness=1, color=(0, 0, 0)):
    """White-outlined text so it's readable on any background colour."""
    cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, size,
                (255, 255, 255), thickness + 2, cv2.LINE_AA)
    cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, size,
                color, thickness, cv2.LINE_AA)


def draw_hover_arc(frame, cx, cy, fraction,
                   color=(0, 255, 180), radius=22, thickness=3):
    """
    Draw a partial arc (countdown ring) at (cx, cy).
    fraction: 0.0 (empty) → 1.0 (full circle).
    """
    angle = int(360 * fraction)
    cv2.ellipse(frame, (cx, cy), (radius, radius),
                -90, 0, angle, color, thickness, cv2.LINE_AA)
