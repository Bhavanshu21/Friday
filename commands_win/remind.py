"""Reminders for the Windows build — scheduled via Task Scheduler, shown as toasts.

"remind me in 20 minutes to stretch" creates a one-time scheduled task
named FRIDAY_reminder_<timestamp> that fires a toast even if FRIDAY is closed.
"""
import datetime
import json
import os
import re
from pathlib import Path

from common import data_dir, run

TASK_PREFIX = "FRIDAY_reminder_"
STORE_FILE = os.path.join(data_dir(), "reminders.json")
NOTIFY_SCRIPT = str(Path(__file__).resolve().parent / "_remind_notify.py")


def _store():
    try:
        with open(STORE_FILE) as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_store(d):
    with open(STORE_FILE, "w") as f:
        json.dump(d, f, indent=1)


def _parse_when(text):
    """Parse 'in 20 minutes', 'at 5pm', 'tomorrow at 9am'. Returns (datetime, error)."""
    now = datetime.datetime.now()
    t = (text or "").strip().lower()

    m = re.fullmatch(r"in\s+(\d+)\s*(minutes?|hours?)", t)
    if m:
        n = int(m.group(1))
        delta = datetime.timedelta(minutes=n if "minute" in m.group(2)
                                   else n * 60)
        return now + delta, ""

    m = re.fullmatch(r"(tomorrow\s+)?at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t)
    if m:
        h, mi, ap = int(m.group(2)), int(m.group(3) or 0), m.group(4)
        if mi > 59:
            return None, f"Bad time {text!r}."
        if ap == "pm" and h < 12:
            h += 12
        elif ap == "am" and h == 12:
            h = 0
        dt = now.replace(hour=h % 24, minute=mi, second=0, microsecond=0)
        if m.group(1):  # tomorrow
            dt += datetime.timedelta(days=1)
        elif dt <= now:
            # "at 5" with no am/pm: try the 12-hour flip before giving up today
            if not ap:
                dt += datetime.timedelta(hours=12)
            if dt <= now:
                dt += datetime.timedelta(days=1)
        return dt, ""

    return None, (f"Couldn't parse {text!r} — try 'in 20 minutes', "
                  "'at 5pm', or 'tomorrow at 9am'.")


def _remind(params):
    text = (params.get("text") or "").strip().strip("\"'")
    if not text:
        return "Remind you to do what? Give me the reminder text too."
    dt, err = _parse_when(params.get("when"))
    if err:
        return err
    if (dt - datetime.datetime.now()).total_seconds() < 60:
        return "Give me at least a minute of lead time."
    name = TASK_PREFIX + dt.strftime("%Y%m%d_%H%M%S")
    tr = f'pythonw.exe "{NOTIFY_SCRIPT}" "{text}"'
    out = run(["schtasks", "/create", "/tn", name, "/tr", tr,
               "/sc", "once", "/st", dt.strftime("%H:%M"),
               "/sd", dt.strftime("%m/%d/%Y"), "/f"], timeout=30)
    if "SUCCESS" not in out.upper():
        return f"Couldn't schedule that: {out}"
    d = _store()
    d[name] = {"text": text, "when": dt.strftime("%Y-%m-%d %H:%M")}
    _save_store(d)
    return f"Reminder set for {dt.strftime('%a %H:%M')}: {text}"


def _list(params):
    d = _store()
    now = datetime.datetime.now()
    live = {}
    for name, r in d.items():
        try:
            dt = datetime.datetime.strptime(r["when"], "%Y-%m-%d %H:%M")
        except (KeyError, ValueError):
            continue
        if dt > now:
            live[name] = r
        else:
            run(["schtasks", "/delete", "/tn", name, "/f"], timeout=30)
    if len(live) != len(d):
        _save_store(live)
    if not live:
        return "No reminders set."
    lines = [f"  {r['when']} — {r['text']}" for r in
             sorted(live.values(), key=lambda r: r["when"])]
    return "Reminders:\n" + "\n".join(lines)


def _cancel(params):
    want = (params.get("text") or params.get("name") or "").strip().lower()
    if not want:
        return "Which reminder? Give me part of its text."
    d = _store()
    hit = None
    for name, r in d.items():
        if want in r.get("text", "").lower() or want in name.lower():
            hit = name
            break
    if not hit:
        return f"No reminder matching {want!r}."
    run(["schtasks", "/delete", "/tn", hit, "/f"], timeout=30)
    d.pop(hit, None)
    _save_store(d)
    return f"Cancelled: {d.get(hit, {}).get('text', hit)}"


TOOLS = [
    {"name": "remind",
     "description": "Set a reminder — shows a Windows toast at the time, even if FRIDAY is closed. "
                    "Usage: remind me in 20 minutes to stretch.",
     "triggers": ["remind me", "reminder", "set reminder", "remind"],
     "parameters": {"type": "OBJECT", "properties": {
         "when": {"type": "STRING", "description": "'in 20 minutes', 'at 5pm', 'tomorrow at 9am'"},
         "text": {"type": "STRING", "description": "what to remind about"}}},
     "arg_patterns": {"when": r"(in\s+\d+\s*(?:minutes?|hours?)|(?:tomorrow\s+)?at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
                      "text": r"(?:to|that|about)\s+(.+)$"},
     "handler": _remind},
    {"name": "reminders",
     "description": "List upcoming reminders.",
     "triggers": ["list reminders", "my reminders", "show reminders", "what reminders"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _list},
    {"name": "reminder_cancel",
     "description": "Cancel a reminder by part of its text.",
     "triggers": ["cancel reminder", "delete reminder", "remove reminder"],
     "parameters": {"type": "OBJECT", "properties": {
         "text": {"type": "STRING", "description": "part of the reminder text to match"}}},
     "handler": _cancel},
]
