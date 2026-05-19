"""
voice.py — Always-on offline voice recognition (Vosk) and command dispatcher.

Wake word: every command starts with "computer".
Press M in the main window to mute/unmute without stopping the thread.
"""
import json
import os
import queue
import subprocess
import threading
import urllib.request
import zipfile

import pyautogui

from config import (VOICE_COMMANDS, VOICE_COOLDOWN, MIC_GAIN,
                    VOSK_MODEL_URL, VOSK_MODEL_DIR, VOSK_MODEL_ZIP)

try:
    import sounddevice as sd
    import vosk
    VOICE_AVAILABLE = True
except ImportError as e:
    print(f"[voice] disabled: {e}")
    VOICE_AVAILABLE = False


def ensure_vosk_model():
    if os.path.isdir(VOSK_MODEL_DIR):
        return True
    print("Downloading Vosk model (~50 MB) ...")
    try:
        urllib.request.urlretrieve(VOSK_MODEL_URL, VOSK_MODEL_ZIP)
        print("Extracting ...")
        with zipfile.ZipFile(VOSK_MODEL_ZIP, "r") as z:
            z.extractall(".")
        os.remove(VOSK_MODEL_ZIP)
        print("Done.")
        return True
    except Exception as e:
        print(f"[voice] model download failed: {e}")
        return False


class VoiceWorker:
    """
    Runs Vosk speech recognition in a background thread.
    Recognised commands are placed on command_queue for the main loop to execute.
    """

    def __init__(self, command_queue):
        self.command_queue = command_queue
        self.stop_event    = threading.Event()
        self.thread        = None
        self.status        = "init"
        self.last_partial  = ""
        self.muted         = False

    def start(self):
        if not VOICE_AVAILABLE:
            self.status = "unavailable (import failed)"
            return False
        if not ensure_vosk_model():
            self.status = "unavailable (model download failed)"
            return False
        try:
            dev = sd.query_devices(kind="input")
            print(f"[voice] using mic: {dev['name']}")
        except Exception as e:
            print(f"[voice] could not query mic: {e}")
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.stop_event.set()

    def _run(self):
        try:
            import numpy as np
            vosk.SetLogLevel(-1)
            model   = vosk.Model(VOSK_MODEL_DIR)
            grammar = json.dumps(list(VOICE_COMMANDS.keys()) + ["[unk]"])
            rec     = vosk.KaldiRecognizer(model, 16000, grammar)
            audio_q = queue.Queue()

            _cb_count = [0]
            def callback(indata, frames, time_info, status):
                arr = np.frombuffer(indata, dtype=np.int16).astype(np.float32)
                arr = np.clip(arr * MIC_GAIN, -32768, 32767).astype(np.int16)
                audio_q.put(arr.tobytes())
                _cb_count[0] += 1
                if _cb_count[0] % 40 == 0:
                    rms = float(np.sqrt(np.mean(arr.astype(np.float32) ** 2)))
                    print(f"[voice] mic level: {rms:.0f}  (target >300)")

            self.status = "listening"
            with sd.RawInputStream(samplerate=16000, blocksize=4000,
                                   dtype="int16", channels=1,
                                   callback=callback):
                while not self.stop_event.is_set():
                    try:
                        data = audio_q.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        text   = result.get("text", "").strip()
                        if text and text != "[unk]":
                            print(f"[voice heard] '{text}'")
                            if text in VOICE_COMMANDS and not self.muted:
                                self.command_queue.put(text)
                                self.last_partial = ""
                            else:
                                self.last_partial = f"? {text}"
                    else:
                        partial = json.loads(rec.PartialResult())
                        self.last_partial = partial.get("partial", "")
        except Exception as e:
            self.status = f"error: {e}"
            print(f"[voice] thread error: {e}")


def execute_voice_command(text):
    """Dispatch a recognised voice command to the OS."""
    spec = VOICE_COMMANDS.get(text)
    if spec is None:
        return
    kind = spec[0]
    try:
        if kind == "launch":
            subprocess.Popen(spec[1], shell=True)
        elif kind == "key":
            pyautogui.press(spec[1])
        elif kind == "key_repeat":
            for _ in range(spec[2]):
                pyautogui.press(spec[1])
        elif kind == "hotkey":
            pyautogui.hotkey(*spec[1])
        print(f"[voice] {text}")
    except Exception as e:
        print(f"[voice failed] {text}: {e}")
