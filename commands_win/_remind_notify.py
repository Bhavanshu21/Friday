"""One-shot toast for a fired reminder. Run by Task Scheduler, not by FRIDAY.

Loader skips this file (leading underscore) — it is not a command.
Usage: pythonw.exe _remind_notify.py "Drink water"
"""
import subprocess
import sys


def main():
    text = sys.argv[1] if len(sys.argv) > 1 else "Reminder"
    try:
        from win11toast import toast
        toast("FRIDAY reminder", text, duration="long")
    except ImportError:
        # fallback: plain message box, no extra dependency
        subprocess.run(["msg", "*", text])


if __name__ == "__main__":
    main()
