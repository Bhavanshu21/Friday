"""
Shared helpers for JARVIS commands.

Everything a command file needs: safe subprocess execution, logging,
user detection, tool availability checks. No dependencies beyond stdlib.
"""
import subprocess
import shutil
import os
import datetime

LOG_DIR = os.path.expanduser("~/.jarvis")
LOG_FILE = os.path.join(LOG_DIR, "jarvis.log")


def log(action):
    """Append an audit line. Never raises — logging must not break the assistant."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {action}\n")
    except OSError:
        pass


def run(args, timeout=60):
    """
    Run ONE allowlisted command. args MUST be a list — never a shell string,
    never shell=True. Returns printable output.
    """
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return f"That tool isn't installed ({args[0]})."
    except subprocess.TimeoutExpired:
        return "Command timed out."
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    if p.returncode != 0 and not out:
        return f"Command failed: {err or 'unknown error'}"
    return out if out else "(no output)"


def launch_detached(args):
    """
    Start a GUI or long-lived program without waiting for it.
    Used for things like Burp Suite that don't produce terminal output.
    """
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except FileNotFoundError:
        return f"That tool isn't installed ({args[0]})."
    return None


def need(tool):
    """True if an external tool exists on PATH."""
    return shutil.which(tool) is not None


def get_user():
    try:
        return os.getlogin()
    except OSError:
        return os.environ.get("USER") or os.environ.get("USERNAME") or "sir"
