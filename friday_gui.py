"""
FRIDAY HUD — Tony Stark-style graphical interface.

Same engine as friday.py (registry, brain, voice, dispatcher), new face:
a live arc-reactor visualizer, transcript, and text/mic input.

Threading: tkinter is not thread-safe. Every blocking operation (brain,
STT, TTS) runs in a daemon worker thread; results travel back through a
queue that the main loop pumps with root.after().
"""
import math
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext
from pathlib import Path

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import friday as cli  # match, extract_params, dispatch, normalize, suggest...
from common import log, get_user

# ------------------------------------------------------------------- palette
BG       = "#04070d"
PANEL    = "#0a1626"
CYAN     = "#00d8ff"
CYAN_DIM = "#0a4d68"
TEXT_FG  = "#d7f4ff"
USER_FG  = "#7ce7ff"
DIM_FG   = "#5b7a8c"
AMBER    = "#ffc857"

STATE_COLORS = {"idle": DIM_FG, "listening": AMBER,
                "thinking": CYAN, "speaking": "#aef7ff"}


def _lerp_color(h1, h2, f):
    a = tuple(int(h1[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(h2[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * f) for x, y in zip(a, b))


# ------------------------------------------------------------------- engine
class Engine:
    """The CLI dispatch pipeline, minus stdin/stdout."""

    EXIT_WORDS = ("exit", "quit", "bye", "goodbye", "power down",
                  "power off", "goodnight", "good night")

    def __init__(self, ui):
        self.ui = ui
        self.registry = cli.REGISTRY
        self.context = cli.CONTEXT
        self.history = []
        self.user = get_user()
        self.brain = None
        self.voice = None
        self._init_brain()
        self._init_voice()

    # -- setup -------------------------------------------------------
    def _init_brain(self):
        try:
            from brain import Brain, DEFAULT_MODEL, DEFAULT_URL
            b = Brain(model=DEFAULT_MODEL,
                      base_url=os.environ.get("FRIDAY_BRAIN_URL")
                      or DEFAULT_URL)
            ok, reason = b.available()
            if ok:
                self.brain = b
            else:
                self.ui.note(f"[brain] {reason} — keyword mode.")
        except Exception as e:
            self.ui.note(f"[brain] unavailable ({e}) — keyword mode.")

    def _init_voice(self):
        try:
            from voice import VoiceIO
            v = VoiceIO()
            v.check_deps()
            self.voice = v
        except Exception as e:
            self.ui.note(f"[voice] {e} — mic disabled, text still works.")
            self.voice = None

    # -- dispatch ----------------------------------------------------
    def resolve(self, text):
        """Mirror of friday.main.resolve: brain, refusal fallback, keywords."""
        if self.brain is not None:
            kind, a, b = self.brain.choose(text, self.registry, self.history)
            if kind == "tool":
                return ("cmd", self.registry[a], b)
            if kind == "chat":
                cmd = cli.match(text)
                if cmd is not None and cli._looks_like_refusal(a):
                    log(f"BRAIN-OVERRIDE: {text!r} -> {cmd['name']}")
                    return ("cmd", cmd, cli.extract_params(cmd, text))
                return ("chat", a)
            # "unavailable" -> fall through to keyword matcher
        cmd = cli.match(text)
        if cmd is None:
            return ("none", None)
        return ("cmd", cmd, cli.extract_params(cmd, text))

    def handle(self, raw):
        """Runs in a worker thread. UI contact only via ui.* (queued)."""
        text = cli.normalize(raw)
        if not text:
            return
        if text in self.EXIT_WORDS:
            self.ui.transcript(f"{self.user}: {raw}", "user")
            self.respond("Powering down. Goodbye.")
            self.ui.shutdown()
            return
        self.ui.transcript(f"{self.user}: {raw}", "user")
        self.ui.set_state("thinking")
        kind, *rest = self.resolve(text)
        if kind == "none":
            hint = cli.suggest(text)
            log(f"UNKNOWN: {raw!r}")
            self.history.append({"role": "user", "content": raw})
            if hint:
                self.respond(f"Not in my repertoire yet. Did you mean "
                             f"something like '{hint}'? (Try 'help'.)")
            else:
                self.respond("Not in my repertoire yet. I only run "
                             "pre-approved commands — try 'help' to see them.")
        elif kind == "chat":
            chat_text = rest[0]
            self.history.append({"role": "user", "content": raw})
            self.history.append({"role": "assistant", "content": chat_text})
            self.respond(chat_text)
        else:
            cmd, params = rest
            log(f"RUN: {cmd['name']}  ({raw!r})  params={params or '{}'}")
            try:
                result = cli.dispatch(cmd, params)
            except Exception as e:  # a command must never kill the assistant
                result = f"Something went wrong running that: {e}"
            self.context.push(cmd["name"], raw, params, result)
            self.history.append({"role": "user", "content": raw})
            self.history.append({"role": "assistant",
                                 "content": f"[ran {cmd['name']}]"})
            self.respond(result)

    def respond(self, text):
        self.ui.transcript(f"FRIDAY: {text}", "friday")
        if self.voice and text:
            self.ui.set_state("speaking")
            stop = threading.Event()
            self.ui.queue.put(("speech_start", stop))
            try:
                self.voice.speak(text, stop_event=stop)
            finally:
                self.ui.queue.put(("speech_end",))
        self.ui.set_state("idle")


# ------------------------------------------------------------------ reactor
class Reactor(tk.Canvas):
    """Arc-reactor visualizer. Set .state to idle/listening/thinking/speaking."""

    def __init__(self, master, size=340):
        super().__init__(master, width=size, height=size, bg=BG,
                         highlightthickness=0, bd=0)
        self.size = size
        self.c = size // 2
        self.state = "idle"
        self.t = 0
        self.seg_offset = 0
        self._gradient = [_lerp_color("#0a4d68", "#c8f6ff", i / 23)
                          for i in range(24)]
        self._draw_static()
        self.after(50, self._tick)

    def _draw_static(self):
        c = self.c
        for i in range(60):
            a = math.radians(i * 6 - 90)
            major = (i % 5 == 0)
            r1, r2 = 146, 156 if major else 151
            self.create_line(c + r1 * math.cos(a), c + r1 * math.sin(a),
                             c + r2 * math.cos(a), c + r2 * math.sin(a),
                             fill=CYAN if major else CYAN_DIM,
                             width=2 if major else 1, tags="static")
        for r in (140, 96):
            self.create_oval(c - r, c - r, c + r, c + r,
                             outline=CYAN_DIM, width=1, tags="static")

    def _tick(self):
        self.t += 1
        self.delete("dyn")
        c, st = self.c, self.state
        if st == "idle":
            p = (math.sin(self.t * 0.10) + 1) / 2
        elif st == "listening":
            p = (math.sin(self.t * 0.30) + 1) / 2
        elif st == "thinking":
            p = 0.65 + 0.15 * math.sin(self.t * 0.2)
            self.seg_offset = (self.seg_offset + 7) % 360
        else:  # speaking
            p = 0.55 + 0.45 * abs(math.sin(self.t * 0.35))
        col = self._gradient[min(23, int(p * 23))]
        hot = st in ("listening", "thinking", "speaking")

        for r, gcol in ((86, "#06283a"), (76, "#0a4d68"), (68, "#0e6e96")):
            self.create_oval(c - r, c - r, c + r, c + r,
                             outline=gcol, width=6, tags="dyn")
        for i in range(10):
            start = self.seg_offset + i * 36
            self.create_arc(c - 118, c - 118, c + 118, c + 118,
                            start=start, extent=26, style="arc",
                            outline=CYAN if hot else CYAN_DIM,
                            width=5, tags="dyn")
        r = 30 + 8 * p
        self.create_oval(c - r, c - r, c + r, c + r,
                         fill=col, outline="", tags="dyn")
        self.create_oval(c - r - 9, c - r - 9, c + r + 9, c + r + 9,
                         outline=col, width=2, tags="dyn")
        if st == "speaking":
            n, bw, gap = 26, 7, 5
            x0 = c - (n * (bw + gap) - gap) / 2
            base = c + 104
            for i in range(n):
                h = 8 + 44 * abs(math.sin(self.t * 0.28 + i * 0.65))
                x = x0 + i * (bw + gap)
                self.create_rectangle(x, base - h, x + bw, base,
                                      fill=CYAN, outline="", tags="dyn")
        self.after(50, self._tick)


# ---------------------------------------------------------------------- hud
class HUD:
    def __init__(self, root):
        self.root = root
        self.queue = queue.Queue()
        self.busy = False
        self.recording = False
        self._rec_stop = None
        self._speech_event = None

        root.title("FRIDAY")
        root.configure(bg=BG)
        root.geometry("540x800")
        root.minsize(480, 700)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(2, weight=1)

        self.reactor = Reactor(root)
        self.reactor.grid(row=0, column=0, pady=(10, 0))

        self.status = tk.Label(root, text="● IDLE", bg=BG, fg=DIM_FG,
                               font=("Consolas", 12, "bold"))
        self.status.grid(row=1, column=0, pady=(0, 6))

        self.log = scrolledtext.ScrolledText(
            root, bg=BG, fg=TEXT_FG, font=("Consolas", 10),
            wrap="word", relief="flat", state="disabled",
            insertbackground=CYAN)
        self.log.grid(row=2, column=0, sticky="nsew", padx=12, pady=6)
        self.log.tag_config("user", foreground=USER_FG)
        self.log.tag_config("friday", foreground=TEXT_FG)
        self.log.tag_config("note", foreground=DIM_FG,
                            font=("Consolas", 10, "italic"))

        entry_frame = tk.Frame(root, bg=BG)
        entry_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=4)
        entry_frame.grid_columnconfigure(0, weight=1)
        self.entry = tk.Entry(entry_frame, bg=PANEL, fg=TEXT_FG,
                              insertbackground=CYAN, font=("Consolas", 11),
                              relief="flat")
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.entry.bind("<Return>", lambda _e: self.on_send())
        send = tk.Button(entry_frame, text="SEND", bg=PANEL, fg=CYAN,
                         activebackground="#123246", activeforeground=CYAN,
                         font=("Consolas", 11, "bold"), relief="flat",
                         padx=14, command=self.on_send)
        send.grid(row=0, column=1)

        btn_frame = tk.Frame(root, bg=BG)
        btn_frame.grid(row=4, column=0, pady=4)
        self.mic_btn = tk.Button(btn_frame, text="🎤 MIC", bg=PANEL, fg=CYAN,
                                 activebackground="#123246",
                                 activeforeground=CYAN,
                                 font=("Consolas", 11, "bold"), relief="flat",
                                 padx=18, pady=4, command=self.on_mic)
        self.mic_btn.pack(side="left", padx=6)
        stop_btn = tk.Button(btn_frame, text="■ STOP", bg=PANEL, fg=AMBER,
                             activebackground="#123246", activeforeground=AMBER,
                             font=("Consolas", 11, "bold"), relief="flat",
                             padx=18, pady=4, command=self.on_stop)
        stop_btn.pack(side="left", padx=6)

        self.engine = Engine(self)
        footer = (f"{len(self.engine.registry)} commands loaded · "
                  f"{'brain online' if self.engine.brain else 'keyword mode'}")
        tk.Label(root, text=footer, bg=BG, fg=DIM_FG,
                 font=("Consolas", 9)).grid(row=5, column=0, pady=(0, 8))
        if self.engine.voice is None:
            self.mic_btn.configure(state="disabled")

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after_pump = root.after(80, self._pump)
        self.transcript("FRIDAY: Hi sir. FRIDAY online.", "friday")
        threading.Thread(target=self._greet, daemon=True).start()

    # ------------------------------------------------- worker-safe (queued)
    def transcript(self, text, tag="friday"):
        self.queue.put(("transcript", text, tag))

    def note(self, text):
        self.queue.put(("note", text))

    def set_state(self, state, label=None):
        self.queue.put(("state", state, label or state.upper()))

    def shutdown(self):
        self.queue.put(("shutdown",))

    # ------------------------------------------------------------- UI thread
    def _append(self, text, tag):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _pump(self):
        try:
            while True:
                self._handle_msg(self.queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(80, self._pump)

    def _handle_msg(self, msg):
        kind = msg[0]
        if kind == "transcript":
            self._append(msg[1], msg[2])
        elif kind == "note":
            self._append(msg[1], "note")
        elif kind == "state":
            _, state, label = msg
            self.reactor.state = state
            self.status.configure(text="● " + label,
                                  fg=STATE_COLORS.get(state, DIM_FG))
        elif kind == "input":
            self.submit(msg[1])
        elif kind == "record_done":
            self.recording = False
            self.mic_btn.configure(text="🎤 MIC")
        elif kind == "speech_start":
            self._speech_event = msg[1]
        elif kind == "speech_end":
            self._speech_event = None
        elif kind == "shutdown":
            self.root.destroy()

    # -------------------------------------------------------------- actions
    def on_send(self):
        text = self.entry.get().strip()
        self.entry.delete(0, "end")
        self.submit(text)

    def submit(self, text):
        if not text.strip() or self.busy:
            return
        self.busy = True
        threading.Thread(target=self._run_handle, args=(text,),
                         daemon=True).start()

    def _run_handle(self, text):
        try:
            self.engine.handle(text)
        finally:
            self.busy = False

    def on_mic(self):
        if self.engine.voice is None or self.busy:
            return
        if not self.recording:
            self.recording = True
            self._rec_stop = threading.Event()
            self.mic_btn.configure(text="■ STOP")
            self.set_state("listening")
            threading.Thread(target=self._record_worker, daemon=True).start()
        else:
            self._rec_stop.set()

    def _record_worker(self):
        try:
            audio = self.engine.voice.record_until(self._rec_stop)
        except Exception as e:
            self.queue.put(("note", f"[mic] {e}"))
            audio = None
        finally:
            self.queue.put(("record_done",))
        if audio is None:
            self.queue.put(("note", "Didn't catch that — try again."))
            self.queue.put(("state", "idle", "IDLE"))
            return
        self.queue.put(("state", "thinking", "TRANSCRIBING"))
        try:
            text = self.engine.voice.transcribe(audio)
        except Exception as e:
            self.queue.put(("note", f"[stt] {e}"))
            self.queue.put(("state", "idle", "IDLE"))
            return
        if text:
            self.queue.put(("input", text))
        else:
            self.queue.put(("note", "Didn't catch that — try again."))
            self.queue.put(("state", "idle", "IDLE"))

    def on_stop(self):
        if self._speech_event is not None:
            self._speech_event.set()

    def _greet(self):
        if self.engine.voice:
            self.set_state("speaking")
            stop = threading.Event()
            self.queue.put(("speech_start", stop))
            try:
                self.engine.voice.speak("Hi sir. FRIDAY online.",
                                        stop_event=stop)
            finally:
                self.queue.put(("speech_end",))
            self.set_state("idle")

    def on_close(self):
        self.root.destroy()


def main():
    root = tk.Tk()
    HUD(root)
    root.mainloop()


if __name__ == "__main__":
    main()
