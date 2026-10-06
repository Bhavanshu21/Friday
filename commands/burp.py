"""
Burp Suite lifecycle management.

Burp is a GUI tool — there is no meaningful way to drive its scans from
a terminal assistant (that needs Burp Professional's API). So FRIDAY
manages its lifecycle: start it, check if it's running, stop it.
"""
from common import run, need, launch_detached


def _guard():
    if not need("burpsuite"):
        return "Burp Suite isn't installed. On Kali: sudo apt install burpsuite"
    return None


def _running():
    out = run(["pgrep", "-f", "burpsuite"])
    return bool(out and "isn't installed" not in out and out != "(no output)")


def _start():
    g = _guard()
    if g:
        return g
    if _running():
        return "Burp Suite is already running."
    launch_detached(["burpsuite"])
    return "Launching Burp Suite in the background."


def _status():
    g = _guard()
    if g:
        return g
    return ("Burp Suite is running."
            if _running() else "Burp Suite is not running.")


def _stop():
    g = _guard()
    if g:
        return g
    if not _running():
        return "Burp Suite isn't running."
    run(["pkill", "-f", "burpsuite"], timeout=15)
    return "Burp Suite stopped."


TOOLS = [
    {"name": "burp_start",
     "description": "Launch Burp Suite in the background.",
     "triggers": ["burp start", "start burp", "launch burp", "open burp"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _start},
    {"name": "burp_status",
     "description": "Check whether Burp Suite is running.",
     "triggers": ["burp status", "is burp running", "burp running"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _status},
    {"name": "burp_stop",
     "description": "Stop Burp Suite.",
     "triggers": ["burp stop", "stop burp", "close burp", "kill burp"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _stop},
]
