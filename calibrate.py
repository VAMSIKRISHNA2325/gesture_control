"""
calibrate.py — Mouse Mode Auto-Calibration for gesture_launcher.py

Run once before using gesture_launcher.py to tune these constants to your hand:
  MOUSE_DEADBAND_PX      — how much tremor to filter out
  MOUSE_SMOOTHING        — cursor lag / responsiveness
  CLICK_PINCH_RATIO_ON   — how tightly you must pinch to click
  CLICK_PINCH_RATIO_OFF  — how open to release the click

Usage:
  python calibrate.py

Controls:
  SPACE  — skip countdown and start phase early
  ESC    — quit without saving
  ENTER  — confirm and write values to gesture_launcher.py
"""

import math
import re
import time

import cv2
import mediapipe as mp
import pyautogui
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# ---------- CONFIG ----------
LAUNCHER_FILE  = "gesture_launcher.py"
HAND_MODEL_PATH = "hand_landmarker.task"
PHASE_DURATION  = 8.0    # seconds of data collection per phase
COUNTDOWN_SEC   = 3      # countdown between phases

SCREEN_W, SCREEN_H = pyautogui.size()

# Landmark IDs (same as gesture_launcher.py)
WRIST      = 0
THUMB_TIP  = 4
INDEX_TIP  = 8
MIDDLE_MCP = 9


# ---------- HELPERS ----------
def _palm_size(lm):
    dx = lm[MIDDLE_MCP].x - lm[WRIST].x
    dy = lm[MIDDLE_MCP].y - lm[WRIST].y
    return math.hypot(dx, dy)


def _pinch_ratio(lm):
    dx = lm[THUMB_TIP].x - lm[INDEX_TIP].x
    dy = lm[THUMB_TIP].y - lm[INDEX_TIP].y
    p = _palm_size(lm)
    return math.hypot(dx, dy) / p if p > 1e-6 else 1.0


def _thumb_screen(lm, margin=0.15):
    ix, iy = lm[THUMB_TIP].x, lm[THUMB_TIP].y
    nx = max(0.0, min(1.0, (ix - margin) / (1 - 2 * margin)))
    ny = max(0.0, min(1.0, (iy - margin) / (1 - 2 * margin)))
    return nx * SCREEN_W, ny * SCREEN_H


def _percentile(sorted_lst, pct):
    if not sorted_lst:
        return 0.0
    idx = int(len(sorted_lst) * pct / 100)
    return sorted_lst[min(idx, len(sorted_lst) - 1)]


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _read_current(name):
    """Read current value of a constant from gesture_launcher.py."""
    pattern = rf'^{re.escape(name)}\s*=\s*([\d.]+)'
    try:
        with open(LAUNCHER_FILE) as f:
            for line in f:
                m = re.match(pattern, line)
                if m:
                    return float(m.group(1))
    except FileNotFoundError:
        pass
    return None


def _patch_constant(name, value):
    """Overwrite one numeric constant in gesture_launcher.py, preserve comments."""
    with open(LAUNCHER_FILE) as f:
        content = f.read()
    pattern = rf'^({re.escape(name)}\s*=\s*)[\d.]+(\s*(?:#.*)?)$'
    patched = re.sub(pattern, rf'\g<1>{value}\2', content, flags=re.MULTILINE)
    with open(LAUNCHER_FILE, 'w') as f:
        f.write(patched)


# ---------- DRAWING ----------
FONT = cv2.FONT_HERSHEY_SIMPLEX

def _txt(frame, text, pos, size=0.55, thickness=1, color=(0, 0, 0)):
    cv2.putText(frame, text, pos, FONT, size, (255, 255, 255), thickness + 2, cv2.LINE_AA)
    cv2.putText(frame, text, pos, FONT, size, color, thickness, cv2.LINE_AA)


def _bar(frame, x, y, w, h, fraction, bg=(60, 60, 60), fg=(0, 200, 120)):
    cv2.rectangle(frame, (x, y), (x + w, y + h), bg, -1)
    fill = int(w * max(0.0, min(1.0, fraction)))
    if fill > 0:
        cv2.rectangle(frame, (x, y), (x + fill, y + h), fg, -1)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (180, 180, 180), 1)


def _draw_hand(frame, lm):
    connections = [
        (0,1),(1,2),(2,3),(3,4),
        (0,5),(5,6),(6,7),(7,8),
        (5,9),(9,10),(10,11),(11,12),
        (9,13),(13,14),(14,15),(15,16),
        (13,17),(17,18),(18,19),(19,20),(0,17),
    ]
    h, w = frame.shape[:2]
    pts = [(int(lm[i].x * w), int(lm[i].y * h)) for i in range(21)]
    for a, b in connections:
        cv2.line(frame, pts[a], pts[b], (200, 200, 200), 1)
    for x, y in pts:
        cv2.circle(frame, (x, y), 3, (0, 120, 255), -1)


# ---------- PHASES ----------
PHASES = [
    {
        "id": 0,
        "name": "STILL",
        "title": "Phase 1 / 3  —  STILL",
        "instruction": "Hold your right hand perfectly still",
        "metric_label": "Tremor radius",
        "metric_unit": "px",
        "color": (0, 200, 120),
    },
    {
        "id": 1,
        "name": "MOVE",
        "title": "Phase 2 / 3  —  MOVE",
        "instruction": "Move your hand naturally like controlling a cursor",
        "metric_label": "Move speed",
        "metric_unit": "px/frame",
        "color": (0, 140, 255),
    },
    {
        "id": 2,
        "name": "PINCH",
        "title": "Phase 3 / 3  —  PINCH",
        "instruction": "Pinch and release naturally  5-6 times",
        "metric_label": "Pinch ratio",
        "metric_unit": "",
        "color": (180, 80, 255),
    },
]


def run_calibration(landmarker):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open camera.")
        return None

    # Per-phase data buckets
    still_positions  = []   # (sx, sy) screen pixels
    move_speeds      = []   # px per frame
    pinch_ratios     = []   # float 0-1

    frame_idx = 0
    phase_idx = 0           # 0-2 = collecting, 3 = done
    state     = "countdown" # "countdown" | "collecting" | "done"
    state_start = time.time()
    prev_thumb = None
    result = None

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts_ms = int(time.time() * 1000)
        det = landmarker.detect_for_video(mp_img, ts_ms)
        frame_idx += 1

        # Pick rightmost hand as action hand
        lm = None
        if det.hand_landmarks:
            lm = max(det.hand_landmarks, key=lambda x: x[WRIST].x)
            _draw_hand(frame, lm)

        now = time.time()
        elapsed = now - state_start
        key = cv2.waitKey(1) & 0xFF
        if key == 27:          # ESC — quit
            cap.release()
            cv2.destroyAllWindows()
            return None

        # ── STATE: DONE ──────────────────────────────────────────
        if state == "done":
            results = _analyse(still_positions, move_speeds, pinch_ratios)
            _draw_results(frame, results)
            _txt(frame, "ENTER = save to gesture_launcher.py   ESC = discard",
                 (10, h - 15), size=0.42, color=(0, 200, 120))
            cv2.imshow("Calibration", frame)
            if key == 13:   # ENTER
                cap.release()
                cv2.destroyAllWindows()
                return results
            continue

        phase = PHASES[phase_idx]

        # ── STATE: COUNTDOWN ─────────────────────────────────────
        if state == "countdown":
            remaining = COUNTDOWN_SEC - elapsed
            _draw_phase_header(frame, phase, w, h)
            _txt(frame, f"Get ready ...  {math.ceil(remaining)}",
                 (w // 2 - 120, h // 2), size=1.0, thickness=2, color=phase["color"])
            _txt(frame, "SPACE to skip", (w // 2 - 70, h // 2 + 45), size=0.45)
            if elapsed >= COUNTDOWN_SEC or key == 32:
                state = "collecting"
                state_start = time.time()
                prev_thumb = None

        # ── STATE: COLLECTING ─────────────────────────────────────
        elif state == "collecting":
            remaining = PHASE_DURATION - elapsed
            fraction  = elapsed / PHASE_DURATION

            # --- collect ---
            metric_val = 0.0
            if lm is not None:
                if phase["id"] == 0:   # STILL
                    sx, sy = _thumb_screen(lm)
                    still_positions.append((sx, sy))
                    if len(still_positions) > 5:
                        med_x = sorted(p[0] for p in still_positions)[len(still_positions)//2]
                        med_y = sorted(p[1] for p in still_positions)[len(still_positions)//2]
                        metric_val = math.hypot(sx - med_x, sy - med_y)

                elif phase["id"] == 1:   # MOVE
                    sx, sy = _thumb_screen(lm)
                    if prev_thumb is not None:
                        spd = math.hypot(sx - prev_thumb[0], sy - prev_thumb[1])
                        move_speeds.append(spd)
                        metric_val = spd
                    prev_thumb = (sx, sy)

                elif phase["id"] == 2:   # PINCH
                    ratio = _pinch_ratio(lm)
                    pinch_ratios.append(ratio)
                    metric_val = ratio

            # --- draw ---
            _draw_phase_header(frame, phase, w, h)
            # Countdown bar
            _bar(frame, 10, 100, w - 20, 18, fraction, fg=phase["color"])
            _txt(frame, f"{remaining:.1f}s remaining", (w - 160, 115), size=0.42)
            # Metric
            if phase["id"] == 2:
                # Pinch ratio: show filled bar 0→1
                _txt(frame, f"Pinch ratio: {metric_val:.3f}", (10, 145), size=0.5)
                _bar(frame, 10, 155, w - 20, 14, metric_val,
                     fg=(0, 220, 200) if metric_val < 0.20 else (200, 200, 0))
                # Mark threshold lines
                cv2.line(frame, (int((w-20)*0.15)+10, 155),
                         (int((w-20)*0.15)+10, 169), (0, 0, 220), 2)
                cv2.line(frame, (int((w-20)*0.30)+10, 155),
                         (int((w-20)*0.30)+10, 169), (220, 100, 0), 2)
                _txt(frame, "ON", (int((w-20)*0.15)+12, 167), size=0.35)
                _txt(frame, "OFF", (int((w-20)*0.30)+12, 167), size=0.35)
            else:
                unit = phase["metric_unit"]
                _txt(frame, f"{phase['metric_label']}: {metric_val:.1f} {unit}",
                     (10, 145), size=0.5, color=phase["color"])

            _txt(frame, f"Samples: {max(len(still_positions), len(move_speeds), len(pinch_ratios))}",
                 (10, h - 15), size=0.42)

            if elapsed >= PHASE_DURATION:
                phase_idx += 1
                if phase_idx >= len(PHASES):
                    state = "done"
                    state_start = now
                else:
                    state = "countdown"
                    state_start = now
                    prev_thumb = None

        cv2.imshow("Calibration", frame)

    cap.release()
    cv2.destroyAllWindows()
    return None


def _draw_phase_header(frame, phase, w, h):
    cv2.rectangle(frame, (0, 0), (w, 85), (30, 30, 30), -1)
    _txt(frame, phase["title"], (10, 30), size=0.75, thickness=2, color=phase["color"])
    _txt(frame, phase["instruction"], (10, 62), size=0.52)


def _analyse(still_positions, move_speeds, pinch_ratios):
    results = {}

    # ── MOUSE_DEADBAND_PX ────────────────────────────────────────
    old_db = _read_current("MOUSE_DEADBAND_PX")
    if len(still_positions) >= 30:
        xs = sorted(p[0] for p in still_positions)
        ys = sorted(p[1] for p in still_positions)
        med_x = xs[len(xs) // 2]
        med_y = ys[len(ys) // 2]
        displacements = sorted(math.hypot(p[0]-med_x, p[1]-med_y) for p in still_positions)
        p95 = _percentile(displacements, 95)
        new_db = _clamp(math.ceil(p95), 3, 18)
    else:
        new_db = old_db
        results["MOUSE_DEADBAND_PX_warn"] = "Too few still samples — kept old value"
    results["MOUSE_DEADBAND_PX"] = (old_db, int(new_db))

    # ── MOUSE_SMOOTHING ──────────────────────────────────────────
    old_sm = _read_current("MOUSE_SMOOTHING")
    if len(move_speeds) >= 30:
        avg_speed = sum(move_speeds) / len(move_speeds)
        raw_sm = 80.0 / max(avg_speed, 1.0)
        new_sm = round(_clamp(raw_sm, 0.05, 0.28), 3)
    else:
        new_sm = old_sm
        results["MOUSE_SMOOTHING_warn"] = "Too few move samples — kept old value"
    results["MOUSE_SMOOTHING"] = (old_sm, new_sm)

    # ── CLICK_PINCH_RATIO_ON / OFF ───────────────────────────────
    old_on  = _read_current("CLICK_PINCH_RATIO_ON")
    old_off = _read_current("CLICK_PINCH_RATIO_OFF")
    if len(pinch_ratios) >= 30:
        sr = sorted(pinch_ratios)
        pinched_max = _percentile(sr, 25)   # deepest quarter = definitely pinched
        open_min    = _percentile(sr, 75)   # top quarter = definitely open

        new_on  = round(_clamp(pinched_max * 1.20, 0.08, 0.28), 3)
        new_off = round(_clamp(open_min    * 0.85, 0.18, 0.50), 3)
        # enforce minimum hysteresis gap
        if new_off < new_on + 0.08:
            new_off = round(min(new_on + 0.08, 0.50), 3)
    else:
        new_on  = old_on
        new_off = old_off
        results["CLICK_PINCH_warn"] = "Too few pinch samples — kept old values"
    results["CLICK_PINCH_RATIO_ON"]  = (old_on,  new_on)
    results["CLICK_PINCH_RATIO_OFF"] = (old_off, new_off)

    return results


def _draw_results(frame, results):
    h, w = frame.shape[:2]
    # Dark overlay
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    _txt(frame, "CALIBRATION COMPLETE", (w//2 - 170, 45),
         size=0.9, thickness=2, color=(0, 220, 140))

    rows = [
        ("MOUSE_DEADBAND_PX",   "MOUSE_DEADBAND_PX"),
        ("MOUSE_SMOOTHING",     "MOUSE_SMOOTHING"),
        ("CLICK_PINCH_RATIO_ON",  "CLICK_PINCH_RATIO_ON"),
        ("CLICK_PINCH_RATIO_OFF", "CLICK_PINCH_RATIO_OFF"),
    ]
    y = 110
    _txt(frame, f"{'Parameter':<28}{'Old':>8}   {'New':>8}", (30, y), size=0.5)
    y += 8
    cv2.line(frame, (30, y), (w - 30, y), (180, 180, 180), 1)
    y += 20

    for label, key in rows:
        if key not in results:
            continue
        old_v, new_v = results[key]
        changed = old_v is not None and abs(float(old_v) - float(new_v)) > 0.001
        color = (0, 220, 140) if changed else (180, 180, 180)
        arrow = "  →" if changed else "  ="
        _txt(frame, f"{label:<28}{str(old_v):>8}{arrow}  {str(new_v):>6}",
             (30, y), size=0.5, color=color)
        warn_key = key + "_warn"
        if warn_key in results:
            _txt(frame, f"  ⚠ {results[warn_key]}", (30, y + 18), size=0.38,
                 color=(0, 140, 255))
            y += 18
        y += 30

    cv2.line(frame, (30, y), (w - 30, y), (180, 180, 180), 1)


def _save(results):
    NUMERIC_KEYS = [
        "MOUSE_DEADBAND_PX",
        "MOUSE_SMOOTHING",
        "CLICK_PINCH_RATIO_ON",
        "CLICK_PINCH_RATIO_OFF",
    ]
    for key in NUMERIC_KEYS:
        if key in results:
            _, new_v = results[key]
            if new_v is not None:
                _patch_constant(key, new_v)
                print(f"[calibrate] {key} = {new_v}")
    print(f"[calibrate] Saved to {LAUNCHER_FILE}")


# ---------- MAIN ----------
def main():
    import os
    if not os.path.exists(HAND_MODEL_PATH):
        print(f"Hand model not found: {HAND_MODEL_PATH}")
        print("Run gesture_launcher.py first to download it.")
        return

    options = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=HAND_MODEL_PATH),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_tracking_confidence=0.5,
    )
    landmarker = vision.HandLandmarker.create_from_options(options)

    print("Starting calibration — follow on-screen instructions.")
    print("ESC to quit, ENTER to save after all phases complete.")

    results = run_calibration(landmarker)
    landmarker.close()

    if results is not None:
        _save(results)
        print("Done. Re-run gesture_launcher.py to use the new settings.")
    else:
        print("Calibration cancelled — no changes made.")


if __name__ == "__main__":
    main()
