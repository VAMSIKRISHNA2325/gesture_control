"""
gesture.py — Entry point. Run this file to start the app.

    python gesture.py

See README.md for the full gesture reference and configuration guide.
"""
import queue
import time
from collections import deque

import cv2
import mediapipe as mp
import pyautogui
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from config import (SCREEN_W, SCREEN_H, HAND_MODEL_PATH,
                    MODE_SWITCH_HOLD_SECONDS, VOICE_COOLDOWN,
                    ensure_hand_model)
from drawing import draw_hand, draw_text
from landmarks import count_fingers_up
from voice import VoiceWorker, execute_voice_command
from modes import IdleMode, LaunchMode, MediaMode, MouseMode, WindowMode


def split_hands(landmark_list):
    """
    Given all detected hands, return (mode_hand, action_hand).
    Left-most hand = mode selector (left hand in mirrored view).
    Right-most hand = action hand.
    """
    if not landmark_list:
        return None, None
    if len(landmark_list) == 1:
        return None, landmark_list[0]
    landmark_list = sorted(landmark_list, key=lambda lm: lm[0].x)
    return landmark_list[0], landmark_list[1]


def main():
    ensure_hand_model()

    options = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=HAND_MODEL_PATH),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.6,
        min_tracking_confidence=0.5,
    )
    landmarker = vision.HandLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open camera.")
        return

    modes = {
        0: IdleMode(),
        1: LaunchMode(),
        2: MediaMode(),
        3: MouseMode(),
        4: WindowMode(),
    }
    current_mode_key = 1
    current_mode     = modes[current_mode_key]
    current_mode.on_enter()

    candidate_mode  = None
    candidate_start = 0.0

    # FPS tracking
    fps_history     = deque(maxlen=30)
    last_frame_time = time.time()
    last_ts_ms      = 0

    # Voice setup
    voice_q             = queue.Queue()
    voice               = VoiceWorker(voice_q)
    voice.start()
    modes[4].voice      = voice   # WindowMode uses this for mute-fallback gestures
    last_voice_text     = ""
    last_voice_time     = 0.0
    voice_cooldown_until = 0.0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)

            # FPS
            now_frame = time.time()
            fps_history.append(1.0 / max(now_frame - last_frame_time, 1e-6))
            last_frame_time = now_frame
            fps = sum(fps_history) / len(fps_history)

            # MediaPipe detection (strictly monotonic timestamps)
            rgb          = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image     = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            timestamp_ms = max(int(time.time() * 1000), last_ts_ms + 1)
            last_ts_ms   = timestamp_ms
            result       = landmarker.detect_for_video(mp_image, timestamp_ms)
            now          = time.time()

            # Drain voice queue
            while not voice_q.empty():
                text = voice_q.get_nowait()
                if now >= voice_cooldown_until:
                    execute_voice_command(text)
                    last_voice_text      = text
                    last_voice_time      = now
                    voice_cooldown_until = now + VOICE_COOLDOWN

            mode_lm, action_lm = split_hands(result.hand_landmarks or [])

            if mode_lm is not None:
                draw_hand(frame, mode_lm, (180, 180, 180), (0, 200, 255))
            if action_lm is not None:
                draw_hand(frame, action_lm, (255, 255, 255), (0, 0, 255))

            # Mode switching (left hand finger count held for 1s)
            switching_to = None
            if mode_lm is not None:
                fcount = count_fingers_up(mode_lm)
                if fcount in modes:
                    if candidate_mode == fcount:
                        if now - candidate_start >= MODE_SWITCH_HOLD_SECONDS:
                            if fcount != current_mode_key:
                                current_mode.on_exit()
                                current_mode_key = fcount
                                current_mode     = modes[fcount]
                                current_mode.on_enter()
                                print(f"[mode] → {current_mode.name}")
                            candidate_mode = None
                        else:
                            switching_to = (fcount, now - candidate_start)
                    else:
                        candidate_mode  = fcount
                        candidate_start = now
                        switching_to    = (fcount, 0.0)
                else:
                    candidate_mode = None
            else:
                candidate_mode = None

            # Run current mode
            mode_info = ""
            if current_mode_key != 0:
                mode_info = current_mode.handle(action_lm, now, frame)

            # ── HUD ──────────────────────────────────────────────────────
            accent = current_mode.color
            cv2.rectangle(frame, (0, 0),
                          (frame.shape[1] - 1, frame.shape[0] - 1), accent, 3)

            draw_text(frame, f"MODE: {current_mode.name}", (10, 30),
                      size=0.8, thickness=2, color=accent)
            draw_text(frame, current_mode.hint, (10, 55), size=0.5)
            if mode_info:
                draw_text(frame, mode_info, (10, 80), size=0.55)

            if switching_to:
                target_key, held = switching_to
                target_name = modes[target_key].name
                bar_w = int(200 * min(1.0, held / MODE_SWITCH_HOLD_SECONDS))
                cv2.rectangle(frame, (10, 105), (210, 120), (80, 80, 80), 1)
                cv2.rectangle(frame, (10, 105), (10 + bar_w, 120),
                              modes[target_key].color, -1)
                draw_text(frame, f"switching to {target_name}", (220, 118), size=0.45)

            # Voice status (top-right)
            voice_label = "MUTED" if voice.muted else voice.status
            voice_color = (0, 0, 220) if voice.muted else (0, 0, 0)
            draw_text(frame, f"VOICE: {voice_label}",
                      (frame.shape[1] - 280, 30), size=0.55, color=voice_color)
            if voice.last_partial and not voice.muted:
                draw_text(frame, f'"{voice.last_partial}"',
                          (frame.shape[1] - 280, 55), size=0.45)
            if last_voice_text and now - last_voice_time < 3.0:
                draw_text(frame, f"> {last_voice_text}",
                          (frame.shape[1] - 280, 80), size=0.5)

            # Cursor minimap (Mouse mode only)
            if current_mode_key == 3:
                cx, cy = pyautogui.position()
                mx, my, mw, mh = frame.shape[1] - 90, 40, 80, 50
                cv2.rectangle(frame, (mx, my), (mx + mw, my + mh), (50, 50, 50), -1)
                cv2.rectangle(frame, (mx, my), (mx + mw, my + mh), (180, 180, 180), 1)
                cv2.circle(frame,
                           (mx + int(cx / SCREEN_W * mw),
                            my + int(cy / SCREEN_H * mh)),
                           3, accent, -1)

            # FPS + bottom bar
            draw_text(frame, f"FPS:{fps:.0f}",
                      (frame.shape[1] - 70, frame.shape[0] - 12), size=0.4)
            draw_text(frame,
                      "Left: 0=IDLE 1=LAUNCH 2=MEDIA 3=MOUSE 4=WINDOW"
                      " | M=mute voice | ESC=quit",
                      (10, frame.shape[0] - 12), size=0.38)

            cv2.imshow("Gesture + Voice Control", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                break
            elif key == ord("m"):
                voice.muted = not voice.muted
                print(f"[voice] {'muted' if voice.muted else 'unmuted'}")

    except KeyboardInterrupt:
        print("Interrupted.")
    except pyautogui.FailSafeException:
        print("Failsafe triggered — move mouse away from top-left corner to re-enable.")
    finally:
        voice.stop()
        cap.release()
        cv2.destroyAllWindows()
        landmarker.close()


if __name__ == "__main__":
    main()
