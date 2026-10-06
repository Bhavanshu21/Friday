"""
Metasploit helpers — non-interactive only.

msfconsole is driven with '-q -x "<commands>; exit"' so each invocation
runs and returns. Interactive exploit sessions don't fit the
run-and-return model, so they stay in msfconsole itself: JARVIS finds
the module, you run it.

The search term / module path is strictly validated — it is embedded in
the -x argument, so anything outside [word chars, /, -] is rejected.
"""
import re
from common import run, need

_SAFE = re.compile(r"^[\w/\-]{1,128}$")


def _guard():
    if not need("msfconsole"):
        return ("msfconsole isn't installed. On Kali: "
                "sudo apt install metasploit-framework")
    return None


def _version():
    g = _guard()
    if g:
        return g
    return run(["msfconsole", "--version"], timeout=60)


def _search(params):
    g = _guard()
    if g:
        return g
    term = (params.get("term") or "").strip()
    if not _SAFE.match(term):
        return ("Usage: msf search <term>  — e.g. 'msf search smb'. "
                "Letters, numbers, / and - only.")
    print(f"Searching Metasploit for '{term}' (msfconsole takes a moment)...")
    return run(["msfconsole", "-q", "-x", f"search {term}; exit"],
               timeout=180)


def _info(params):
    g = _guard()
    if g:
        return g
    module = (params.get("module") or "").strip()
    if not _SAFE.match(module):
        return ("Usage: msf info <module>  — e.g. "
                "'msf info exploit/windows/smb/ms17_010_eternalblue'.")
    print(f"Fetching info for {module}...")
    return run(["msfconsole", "-q", "-x", f"info {module}; exit"],
               timeout=180)


TOOLS = [
    {"name": "msf_version",
     "description": "Show the installed Metasploit version.",
     "triggers": ["msf version", "metasploit version"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _version},
    {"name": "msf_search",
     "description": "Search Metasploit modules. Usage: msf search <term>.",
     "triggers": ["msf search", "metasploit search", "search msf",
                  "search exploit"],
     "arg_patterns": {"term": r"(?:msf search|metasploit search|search msf|search exploit)\s+([\w/\-]+)"},
     "parameters": {"type": "OBJECT",
                    "properties": {"term": {"type": "STRING",
                                            "description": "Search term."}}},
     "handler": _search},
    {"name": "msf_info",
     "description": "Show details of a Metasploit module. Usage: msf info <module path>.",
     "triggers": ["msf info", "metasploit info"],
     "arg_patterns": {"module": r"(?:msf info|metasploit info)\s+([\w/\-]+)"},
     "parameters": {"type": "OBJECT",
                    "properties": {"module": {"type": "STRING",
                                              "description": "Module path."}}},
     "handler": _info},
]
