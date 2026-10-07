"""Open things on screen — folders in Explorer, workbooks in Excel.

os.startfile is Windows-only; this file lives in commands_win/ so it only
loads on win32.
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from common import data_dir

FOLDER_ALIAS_FILE = os.path.join(data_dir(), "folder_aliases.json")
EXCEL_ALIAS_FILE = os.path.join(data_dir(), "excel_aliases.json")


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


def _lookup(aliases, ref):
    for nick, val in aliases.items():
        if nick.lower() == ref.lower():
            return val
    return None


# ------------------------------------------------------------------- folders
def _remember_folder(params):
    nick = (params.get("nickname") or "").strip().lower()
    raw = (params.get("path") or "").strip().strip("\"'")
    if not nick or not raw:
        return ("Say e.g. remember folder dreamvirtment "
                "C:\\Users\\Narayan\\dreamvirtment")
    p = Path(os.path.expandvars(raw)).expanduser()
    if not p.is_dir():
        return f"That folder doesn't exist: {raw}"
    aliases = _load(FOLDER_ALIAS_FILE)
    aliases[nick] = str(p)
    _save(FOLDER_ALIAS_FILE, aliases)
    return f"Remembered folder '{nick}' -> {p}."


def _resolve_folder(ref):
    ref = (ref or "").strip().strip("\"'")
    hit = _lookup(_load(FOLDER_ALIAS_FILE), ref)
    if hit:
        return Path(hit)
    return Path(os.path.expandvars(ref)).expanduser()


def _open_folder(params):
    ref = (params.get("path") or "").strip()
    if not ref:
        return "Which folder? Say e.g. open folder dreamvirtment."
    p = _resolve_folder(ref)
    if not p.is_dir():
        return (f"Folder not found: {ref}. "
                "Save it first: remember folder <name> <full path>.")
    os.startfile(str(p))
    return f"Opened {p}."


# --------------------------------------------------------------------- excel
def _find_excel():
    p = shutil.which("excel.exe")
    if p:
        return p
    for base in (os.environ.get("ProgramFiles", ""),
                 os.environ.get("ProgramFiles(x86)", "")):
        for ver in ("Office16", "Office15", "Office14"):
            p = Path(base) / "Microsoft Office" / "root" / ver / "EXCEL.EXE"
            if p.is_file():
                return str(p)
    return None


def _resolve_workbook(ref):
    ref = (ref or "").strip().strip("\"'")
    hit = _lookup(_load(EXCEL_ALIAS_FILE), ref)
    if hit:
        return Path(hit)
    return Path(os.path.expandvars(ref)).expanduser()


def _open_workbook(params):
    ref = (params.get("workbook") or "").strip()
    if ref:
        p = _resolve_workbook(ref)
        if not p.is_file():
            return (f"Workbook not found: {ref}. "
                    "Save it first: remember sheet <name> <full path>.")
        os.startfile(str(p))  # opens in Excel (default .xlsx handler)
        return f"Opened {p.name} in Excel."
    exe = _find_excel()
    if exe:
        os.startfile(exe)
        return "Opened Excel."
    try:  # last resort: App Paths lookup via the shell
        subprocess.Popen(["cmd", "/c", "start", "", "excel"],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return "Opened Excel."
    except Exception:
        return "Couldn't find Excel. Is Microsoft Office installed?"


TOOLS = [
    {"name": "open_folder",
     "description": "Open a folder in Windows Explorer so you can see it. "
                    "Usage: open folder dreamvirtment (or a full path).",
     "triggers": ["open folder", "show folder", "open directory", "folder"],
     "parameters": {"type": "OBJECT", "properties": {
         "path": {"type": "STRING",
                  "description": "folder nickname or full path"}}},
     "arg_patterns": {"path": [r"\bfolder\s+(.+)$",
                               r"\bopen\s+(?:the\s+)?(.+?)\s+folder$"]},
     "handler": _open_folder},
    {"name": "remember_folder",
     "description": "Save a nickname for a folder, for use with open folder. "
                    "Usage: remember folder dreamvirtment C:\\path\\to\\folder.",
     "triggers": ["remember folder", "save folder"],
     "parameters": {"type": "OBJECT", "properties": {
         "nickname": {"type": "STRING", "description": "short name"},
         "path": {"type": "STRING", "description": "full folder path"}}},
     "arg_patterns": {"nickname": [r"remember folder\s+(\S+)",
                                   r"save folder\s+(\S+)"],
                      "path": [r"remember folder\s+\S+\s+(.+)$",
                               r"save folder\s+\S+\s+(.+)$"]},
     "handler": _remember_folder},
    {"name": "open_workbook",
     "description": "Open an Excel workbook in the Excel desktop app, or "
                    "launch Excel itself when no workbook is named. "
                    "Usage: open excel budget.",
     "triggers": ["open excel", "launch excel", "start excel",
                  "open workbook"],
     "parameters": {"type": "OBJECT", "properties": {
         "workbook": {"type": "STRING",
                      "description": "workbook nickname or .xlsx path "
                                     "(omit to just launch Excel)"}}},
     "arg_patterns": {"workbook": [r"\bexcel\s+(.+)$",
                                   r"\bworkbook\s+(.+)$"]},
     "handler": _open_workbook},
]
