#!/usr/bin/env python3
"""
JARVIS — Phase 2b: voice. Offline STT (faster-whisper) + TTS (Piper).

Run `python3 jarvis.py --voice` for push-to-talk mode (Enter starts/stops
recording). Text mode is unchanged and stays stdlib-only; voice.py and
requirements-voice.txt are the only new dependencies, loaded lazily.

ARCHITECTURE
    jarvis.py      this file — main loop, intent matching, dispatch, help
    common.py      safe subprocess runner, logging, user detection
    loader.py      auto-discovers commands/*.py at startup (the Mark-LV pattern)
    context.py     short-term memory: last N runs, for "again" / "recall"
    commands/      one file per domain; each exposes TOOLS = [{...}, ...]

HOW COMMANDS WORK NOW
    A TOOL dict may declare "arg_patterns": {"host": r"ping\\s+(\\S+)"}.
    The dispatcher extracts named args from the input and passes them to
    handlers that declare a `params` parameter. Handlers that declare `ctx`
    get {"registry", "context"} — used by composite workflow commands.
    Handlers with neither keep working exactly as in Phase 1.

SAFETY DESIGN
    1. ALLOWLIST ONLY. The registry built by loader.py is the entire set of
       things that can run. The brain never invents shell commands.
    2. NO shell=True ANYWHERE. common.run() takes argument arrays only.
    3. TIMEOUTS on every command.
    4. DESTRUCTIVE commands (reboot) ask for confirmation first.
    5. Every extracted argument is validated by its command before use —
       raw user text never reaches a subprocess unfiltered.
    6. Everything run is logged to ~/.jarvis/jarvis.log.

WHAT WAS LEFT OUT (deliberately)
    - No cloud LLM / API keys — fully offline.
    - No GUI/avatar — this is a terminal tool for a VM.
    - No undo stack yet — arrives with the first file-changing command.
"""
import re
import difflib
import inspect
import argparse
from pathlib import Path

from common import log, get_user
from loader import discover_commands
from context import RunContext

BASE = Path(__file__).resolve().parent
REGISTRY, REPORT = discover_commands(BASE / "commands")
for _file, _ok, _msg in REPORT:
    if not _ok:
        print(f"[loader] {_file}: {_msg}")

CONTEXT = RunContext()


def normalize(text):
    text = text.lower()
    text = re.sub(r"\bjarvis\b", "", text)          # wake word is optional
    text = re.sub(r"\bplease\b", "", text)
    # strip punctuation only at the edges — mid-string dots belong to
    # IPs and hostnames ("ping 8.8.8.8" must survive intact)
    text = re.sub(r"^[?.!,]+", "", text)
    text = re.sub(r"[?.!,]+$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def match(text):
    """
    Longest matching trigger wins; ties break by earliest position, so
    the leading verb wins ('service ssh restart' -> service, not reboot).
    Word boundaries stop 'hi' matching inside 'machine'.
    """
    best, best_key = None, None
    for cmd in REGISTRY.values():
        for trig in cmd["triggers"]:
            m = re.search(r"\b" + re.escape(trig) + r"\b", text)
            if m:
                key = (-len(trig), m.start())
                if best_key is None or key < best_key:
                    best, best_key = cmd, key
    return best


def extract_params(cmd, text):
    """Fill the command's declared arg_patterns from the input text."""
    params = {}
    for name, pattern in cmd.get("arg_patterns", {}).items():
        m = re.search(pattern, text)
        if m:
            params[name] = m.group(1)
    return params


def dispatch(cmd, params):
    """
    Call a handler, injecting params and/or ctx only if it declares them.
    Phase 1 no-arg handlers keep working unchanged.
    """
    sig = inspect.signature(cmd["handler"])
    kwargs = {}
    if "params" in sig.parameters:
        kwargs["params"] = params
    if "ctx" in sig.parameters:
        kwargs["ctx"] = {"registry": REGISTRY, "context": CONTEXT}
    return cmd["handler"](**kwargs)


def suggest(text):
    """Fuzzy hint when nothing matches."""
    all_triggers = [t for c in REGISTRY.values() for t in c["triggers"]]
    words = text.split()
    best, score = None, 0.0
    for trig in all_triggers:
        for w in words:
            s = difflib.SequenceMatcher(None, w, trig.split()[0]).ratio()
            if s > score:
                best, score = trig, s
    return best if score > 0.6 else None


def cmd_help():
    lines = ["Here's what I can do:"]
    for cmd in REGISTRY.values():
        if cmd["name"] in ("greeting", "joke", "clear"):
            continue
        lines.append(f"  - {cmd['description']}")
    lines.append("  (Try: 'update my system', 'nmap quick 192.168.1.1', "
                 "'health check', 'msf search smb')")
    return "\n".join(lines)


def handle_again():
    """Re-run the last command with its original params."""
    last = CONTEXT.last()
    if not last:
        return "Nothing to repeat yet — give me a command first."
    cmd = REGISTRY.get(last["command"])
    if not cmd:
        return "The last command is no longer loaded."
    log(f"REPEAT: {last['command']}  ({last['input']!r})")
    try:
        result = dispatch(cmd, last["params"])
    except Exception as e:
        result = f"Something went wrong running that: {e}"
    CONTEXT.push(last["command"], last["input"], last["params"], result)
    return result


def handle_recall_ip():
    ip = CONTEXT.find_ip()
    if ip:
        return f"The last IP address I showed was {ip}."
    return "I haven't shown any IP address yet this session."


def main():
    ap = argparse.ArgumentParser(description="JARVIS — offline assistant")
    ap.add_argument("--voice", action="store_true",
                    help="voice mode: push-to-talk input, spoken output")
    args = ap.parse_args()

    voice = None
    if args.voice:
        try:
            from voice import VoiceIO
            voice = VoiceIO()
            voice.check_deps()
        except RuntimeError as e:
            print(e)
            print("Voice mode needs its dependencies — see README, Phase 2b.")
            return
        print("[voice] push-to-talk ready: Enter starts/stops recording.\n")

    if voice:
        def get_input(prompt):
            print(prompt, end=" ", flush=True)
            return voice.listen()

        def say(text):
            text = text or ""
            if text:
                print(text)
            if text.strip():
                # never speak walls of text — the screen keeps the full output
                short = (text if len(text) <= 600
                         else text[:600] + " ... (truncated for speech; "
                                           "full output on screen)")
                try:
                    voice.speak(short)
                except RuntimeError as e:
                    print(e)
    else:
        def get_input(prompt):
            return input(prompt)

        def say(text):
            if text:
                print(text)

    user = get_user()
    n = len(REGISTRY)
    say(f"JARVIS online — {n} commands loaded from commands/.")
    if not voice:
        print("Type 'help' to see what I can do, 'exit' to power down.\n")
    else:
        print("Say 'help' to hear what I can do, 'exit' to power down.\n")

    while True:
        try:
            raw = get_input(f"{user} ➜ ").strip()
        except (EOFError, KeyboardInterrupt):
            say("\nPowering down. Goodbye.")
            break
        if not raw:
            continue
        text = normalize(raw)

        if text in ("exit", "quit", "bye", "goodbye", "power down",
                    "power off", "goodnight", "good night"):
            say("Powering down. Goodbye.")
            break
        if text in ("help", "what can you do", "commands", "list commands"):
            say(cmd_help())
            print()
            continue
        if text in ("again", "repeat", "do it again", "run it again",
                     "one more time"):
            result = handle_again()
            say(result)
            print()
            continue
        if text in ("what was the ip", "recall ip", "what ip",
                     "what was that ip"):
            say(handle_recall_ip())
            print()
            continue

        cmd = match(text)
        if cmd is None:
            hint = suggest(text)
            log(f"UNKNOWN: {raw!r}")
            if hint:
                say(f"Not in my repertoire yet. Did you mean something "
                    f"like '{hint}'? (Try 'help'.)")
            else:
                say("Not in my repertoire yet. I only run pre-approved "
                    "commands — try 'help' to see them.")
            print()
            continue

        params = extract_params(cmd, text)
        log(f"RUN: {cmd['name']}  ({raw!r})  params={params or '{}'}")
        try:
            result = dispatch(cmd, params)
        except Exception as e:  # a command must never kill the assistant
            result = f"Something went wrong running that: {e}"
        CONTEXT.push(cmd["name"], raw, params, result)
        say(result)
        print()


if __name__ == "__main__":
    main()
