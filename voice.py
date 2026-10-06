"""
JARVIS Phase 2b — offline voice I/O: faster-whisper (STT) + Piper (TTS).

Push-to-talk: press Enter to start recording, press Enter again to stop.
Models live under ~/.jarvis/models and download on first use.

    System deps (Kali):  sudo apt install libportaudio2 espeak-ng
    Python deps:         pip install -r requirements.txt

Text mode never imports this file, so it stays stdlib-only and instant.
Every heavy import is lazy and raises a clear error naming what's missing.
"""
import importlib
import shutil
import sys
import threading
import urllib.request
import wave
from pathlib import Path

MODEL_DIR = Path.home() / ".jarvis" / "models"
SAMPLE_RATE = 16000          # what Whisper expects
PIPER_VOICE = "en_US-lessac-medium"
PIPER_BASE_URL = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/"
                  "en/en_US/lessac/medium/en_US-lessac-medium")


def _require(module, pip_name, sys_pkg=None):
    """Import or raise a clear, actionable error."""
    try:
        return importlib.import_module(module)
    except ImportError:
        hint = f"[voice] missing '{module}'. Run:  pip install {pip_name}"
        if sys_pkg:
            hint += f"\n[voice] plus the system library:  sudo apt install {sys_pkg}"
        raise RuntimeError(hint)


class VoiceIO:
    def __init__(self, stt_model="base"):
        self.stt_model = stt_model
        self._stt = None
        self._tts = None
        self._onnx = MODEL_DIR / f"{PIPER_VOICE}.onnx"
        self._onnx_json = MODEL_DIR / f"{PIPER_VOICE}.onnx.json"

    # ------------------------------------------------------------------ setup
    def check_deps(self):
        _require("faster_whisper", "faster-whisper")
        _require("piper", "piper-tts", "espeak-ng")
        _require("sounddevice", "sounddevice", "libportaudio2")
        _require("numpy", "numpy")
        if shutil.which("espeak-ng") is None:
            raise RuntimeError("[voice] espeak-ng not found. "
                               "Run:  sudo apt install espeak-ng")

    def _ensure_voice_files(self):
        if self._onnx.exists() and self._onnx_json.exists():
            return
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        for url, dest in ((PIPER_BASE_URL + ".onnx", self._onnx),
                          (PIPER_BASE_URL + ".onnx.json", self._onnx_json)):
            if dest.exists():
                continue
            print(f"[voice] downloading {dest.name} (~60MB)...")
            urllib.request.urlretrieve(url, dest)

    # --------------------------------------------------------------------- STT
    def transcribe(self, audio, language="en"):
        """Transcribe a 16kHz mono float32 numpy array. Returns text."""
        fw = _require("faster_whisper", "faster-whisper")
        if self._stt is None:
            print(f"[voice] loading whisper '{self.stt_model}' "
                  f"(first run downloads the model)...")
            self._stt = fw.WhisperModel(self.stt_model, device="cpu",
                                        compute_type="int8")
        segments, _info = self._stt.transcribe(audio, beam_size=5,
                                               language=language)
        return "".join(s.text for s in segments).strip()

    def _save_debug_wav(self, audio):
        """Keep the last recording so the user can hear what STT heard."""
        np = _require("numpy", "numpy")
        path = MODEL_DIR / "last_recording.wav"
        pcm16 = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm16.tobytes())
        return path

    def listen(self):
        """
        Push-to-talk: Enter starts recording, Enter stops it.
        Or just TYPE a command at the prompt to skip the mic entirely.
        Returns the transcribed/typed text ("" if nothing usable was said).
        """
        typed = input("Press Enter and speak (Enter again to stop), "
                      "or type a command... ").strip()
        if typed:
            return typed  # text fallback — no mic needed

        sd = _require("sounddevice", "sounddevice", "libportaudio2")
        np = _require("numpy", "numpy")

        print("Recording... press Enter to stop.")
        frames, stop = [], threading.Event()

        def _wait_for_enter():
            try:
                input()
            except EOFError:
                pass
            stop.set()

        threading.Thread(target=_wait_for_enter, daemon=True).start()

        def _cb(indata, nframes, time, status):
            frames.append(indata.copy())

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                            dtype="float32", callback=_cb):
            stop.wait()

        if not frames:
            return ""
        audio = np.concatenate(frames, axis=0).reshape(-1)
        if audio.size < SAMPLE_RATE // 2:      # under 0.5s: accidental tap
            print("[voice] too short — ignored.")
            return ""
        dbg = self._save_debug_wav(audio)
        print(f"[voice] transcribing... (saved {dbg})")
        return self.transcribe(audio)

    # --------------------------------------------------------------------- TTS
    def speak(self, text):
        """Synthesize text with Piper and play it. Silent on empty text."""
        text = (text or "").strip()
        if not text:
            return
        piper = _require("piper", "piper-tts", "espeak-ng")
        self._ensure_voice_files()
        if self._tts is None:
            print("[voice] loading Piper voice...")
            self._tts = piper.PiperVoice.load(str(self._onnx))
        wav_path = MODEL_DIR / "speech.wav"
        with wave.open(str(wav_path), "wb") as wf:
            self._tts.synthesize_wav(text, wf)
        self._play(wav_path)

    def _play(self, wav_path):
        sd = _require("sounddevice", "sounddevice", "libportaudio2")
        np = _require("numpy", "numpy")
        with wave.open(str(wav_path), "rb") as wf:
            raw = wf.readframes(wf.getnframes())
            sr, ch, sw = wf.getframerate(), wf.getnchannels(), wf.getsampwidth()
        if sw != 2:
            raise RuntimeError(f"[voice] unexpected wav format ({sw * 8}-bit)")
        audio = np.frombuffer(raw, dtype=np.int16)
        if ch > 1:
            audio = audio.reshape(-1, ch)
        sd.play(audio, samplerate=sr)
        self._wait_interruptible(sd, len(audio) / sr)

    @staticmethod
    def _wait_interruptible(sd, seconds):
        """
        Block until playback ends. ESC stops it early.
        Stdlib only (termios/select) — no extra dependencies.
        """
        import select
        import termios
        import time
        import tty
        if not sys.stdin.isatty():
            sd.wait()
            return
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        deadline = time.time() + seconds + 0.5
        print("[voice] speaking... (ESC to stop)")
        try:
            tty.setcbreak(fd)  # single keypresses, no Enter needed
            while time.time() < deadline:
                r, _, _ = select.select([fd], [], [], 0.15)
                if not r:
                    continue
                if sys.stdin.read(1) == "\x1b":
                    # swallow the rest of any escape sequence (arrow keys, etc.)
                    while select.select([fd], [], [], 0.05)[0]:
                        sys.stdin.read(1)
                    sd.stop()
                    print("[voice] stopped.")
                    return
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
