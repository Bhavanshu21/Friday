#!/usr/bin/env python3
"""
FRIDAY — Phase 3: the brain. Local Ollama LLM (qwen3:4b) picks tools.

`python3 friday.py --brain ollama` — the model reads the TOOL registry via
Ollama's native tools API and chooses one command per turn. Unknown tool
names are rejected; the registry is still the allowlist. If Ollama isn't
reachable, it falls back to the keyword matcher automatically.
`python3 friday.py --voice --brain ollama` combines both.
`python3 friday.py --brain ollama --model qwen3:1.7b` uses a smaller,
faster model (handy on CPU-only machines).

ARCHITECTURE
    friday.py      this file — main loop, intent matching, dispatch, help
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
    6. Everything run is logged to ~/.friday/friday.log.

WHAT WAS LEFT OUT (deliberately)
    - No cloud LLM / API keys — fully offline.
    - No GUI/avatar — this is a terminal tool for a VM.
    - No undo stack yet — arrives with the first file-changing command.
"""
import re
import os
import sys
import difflib
import inspect
import argparse
from pathlib import Path

from common import log, get_user
from loader import discover_commands
from context import RunContext

BASE = Path(__file__).resolve().parent
# Platform split: Windows loads commands_win/, everything else loads commands/.
# One repo, both platforms — the brain, voice, and dispatcher are identical.
COMMANDS_DIR = "commands_win" if sys.platform == "win32" else "commands"
REGISTRY, REPORT = discover_commands(BASE / COMMANDS_DIR)
for _file, _ok, _msg in REPORT:
    if not _ok:
        print(f"[loader] {_file}: {_msg}")

CONTEXT = RunContext()


def normalize(text):
    text = text.lower()
    text = re.sub(r"\b(?:friday|jarvis)\b", "", text)  # wake word is optional
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
    """Fill the command's declared arg_patterns from the input text.
    A param may declare a list of patterns; the first one that matches wins.
    (Plain strings keep working as before.)"""
    params = {}
    for name, pattern in cmd.get("arg_patterns", {}).items():
        patterns = pattern if isinstance(pattern, list) else [pattern]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                params[name] = m.group(1)
                break
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
    if sys.platform == "win32":
        lines.append("  (Try: 'what's the weather in Delhi', "
                     "'remind me in 20 minutes to stretch', "
                     "'open excel budget')")
    else:
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


_REFUSAL_HINTS = ("can't", "cannot", "don't have", "do not have",
                  "unable to", "no tool", "not able to", "couldn't",
                  "won't be able")


def _looks_like_refusal(text):
    return any(h in (text or "").lower() for h in _REFUSAL_HINTS)


def main():
    ap = argparse.ArgumentParser(description="FRIDAY — offline assistant")
    ap.add_argument("--voice", action="store_true",
                    help="voice mode: push-to-talk input, spoken output")
    ap.add_argument("--brain", choices=["keyword", "ollama"], default="keyword",
                    help="how commands are chosen (default: keyword)")
    ap.add_argument("--model", metavar="MODEL", default=None,
                    help="Ollama model for --brain ollama (default: qwen3:4b; "
                         "e.g. qwen3:1.7b is much faster on CPU-only machines)")
    ap.add_argument("--brain-url", metavar="URL", default=None,
                    help="Ollama server for --brain ollama "
                         "(default: http://localhost:11434, or the "
                         "FRIDAY_BRAIN_URL env var if set; e.g. "
                         "http://10.0.2.2:11434 to use the host PC's Ollama "
                         "from the VM)")
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

    brain = None
    if args.brain == "ollama":
        try:
            from brain import Brain, DEFAULT_MODEL, DEFAULT_URL
            model = args.model or DEFAULT_MODEL
            if args.model and not re.match(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$",
                                           args.model):
                print(f"[brain] invalid model name {args.model!r} — "
                      f"using {DEFAULT_MODEL}.")
                model = DEFAULT_MODEL
            brain = Brain(model=model,
                          base_url=args.brain_url
                          or os.environ.get("FRIDAY_BRAIN_URL")
                          or DEFAULT_URL)
            ok, reason = brain.available()
            if not ok:
                print(f"[brain] {reason} — keyword fallback active.")
                brain = None
            else:
                print(f"[brain] {brain.model} online — tool-calling mode.")
        except Exception as e:
            print(f"[brain] couldn't start ({e}) — keyword fallback active.")
            brain = None

    history = []  # intents only: {"role", "content"} — never tool outputs

    def resolve(text):
        """
        Pick a command. Returns (cmd, params), (("chat", text), None) for a
        plain brain reply, or (None, None) when nothing matches.
        """
        if brain is not None:
            print("[brain] thinking...")
            kind, a, b = brain.choose(text, REGISTRY, history)
            if kind == "tool":
                return REGISTRY[a], b
            if kind == "chat":
                # Safety net: the small local model sometimes insists a tool
                # doesn't exist when it does. If the reply reads like a
                # refusal but the keyword matcher found a genuine trigger,
                # trust the registry over the model.
                cmd = match(text)
                if cmd is not None and _looks_like_refusal(a):
                    log(f"BRAIN-OVERRIDE: {text!r} -> {cmd['name']} "
                        f"(model refused: {a[:80]!r})")
                    return cmd, extract_params(cmd, text)
                return ("chat", a), None
            # "unavailable" -> fall through to keyword matcher
        cmd = match(text)
        if cmd is None:
            return None, None
        return cmd, extract_params(cmd, text)

    say("Hi sir. FRIDAY online.")
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

        resolved, params = resolve(text)
        if resolved is None:
            hint = suggest(text)
            log(f"UNKNOWN: {raw!r}")
            if hint:
                say(f"Not in my repertoire yet. Did you mean something "
                    f"like '{hint}'? (Try 'help'.)")
            else:
                say("Not in my repertoire yet. I only run pre-approved "
                    "commands — try 'help' to see them.")
            history.append({"role": "user", "content": raw})
            print()
            continue
        if isinstance(resolved, tuple) and resolved[0] == "chat":
            chat_text = resolved[1]
            say(chat_text)  # plain brain reply, no tool
            history.append({"role": "user", "content": raw})
            history.append({"role": "assistant", "content": chat_text})
            print()
            continue
        cmd = resolved

        log(f"RUN: {cmd['name']}  ({raw!r})  params={params or '{}'}")
        try:
            result = dispatch(cmd, params)
        except Exception as e:  # a command must never kill the assistant
            result = f"Something went wrong running that: {e}"
        CONTEXT.push(cmd["name"], raw, params, result)
        history.append({"role": "user", "content": raw})
        history.append({"role": "assistant",
                        "content": f"[ran {cmd['name']}]"})
        say(result)
        print()


if __name__ == "__main__":
    main()
