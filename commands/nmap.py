"""
nmap scan profiles. Each is a pre-approved scan shape with a validated
target — the user picks the profile, JARVIS fills in the flags.

Targets must be an IPv4 address, CIDR range, 'localhost', or a dotted
hostname. Anything else is rejected before nmap ever sees it.
"""
import re
from common import run, need

_IPv4 = r"(\d{1,3}(?:\.\d{1,3}){3})"
_HOST = r"[A-Za-z0-9](?:[A-Za-z0-9.\-]*[A-Za-z0-9])?"


def _valid_target(t):
    if not t or len(t) > 253:
        return False
    if t == "localhost":
        return True
    m = re.match(rf"^{_IPv4}(/\d{{1,2}})?$", t)
    if m:
        return all(0 <= int(o) <= 255 for o in m.group(1).split("."))
    m = re.match(rf"^{_HOST}(/\d{{1,2}})?$", t)
    return bool(m) and "." in t


def _target(params):
    t = (params.get("target") or "").strip()
    return t if _valid_target(t) else None


def _usage(name):
    return (f"Usage: nmap {name} <target>  — target is an IP, CIDR like "
            f"192.168.1.0/24, or hostname. E.g. 'nmap {name} 192.168.1.5'.")


def _guard():
    if not need("nmap"):
        return "nmap isn't installed. Run: sudo apt install nmap"
    return None


def _quick(params):
    g = _guard()
    if g:
        return g
    t = _target(params)
    if not t:
        return _usage("quick")
    print(f"Fast scan of {t} (top 100 ports)...")
    return run(["nmap", "-F", t], timeout=180)


def _standard(params):
    g = _guard()
    if g:
        return g
    t = _target(params)
    if not t:
        return _usage("standard")
    print(f"Scanning {t} with version detection and default scripts. "
          f"This takes a few minutes...")
    return run(["nmap", "-sV", "-sC", t], timeout=600)


def _full(params):
    g = _guard()
    if g:
        return g
    t = _target(params)
    if not t:
        return _usage("full")
    print(f"Full port scan of {t} (all 65535 ports). This is slow — "
          f"grab some chai...")
    return run(["nmap", "-sV", "-sC", "-p-", t], timeout=1800)


def _os(params):
    g = _guard()
    if g:
        return g
    t = _target(params)
    if not t:
        return _usage("os")
    print(f"OS detection on {t} (needs sudo)...")
    return run(["sudo", "nmap", "-O", t], timeout=300)


def _udp(params):
    g = _guard()
    if g:
        return g
    t = _target(params)
    if not t:
        return _usage("udp")
    print(f"UDP scan of {t} (top 100 ports, needs sudo). UDP is slow...")
    return run(["sudo", "nmap", "-sU", "--top-ports", "100", t], timeout=900)


def _vuln(params):
    g = _guard()
    if g:
        return g
    t = _target(params)
    if not t:
        return _usage("vuln")
    print(f"Vulnerability script scan of {t}. This takes several minutes...")
    return run(["nmap", "-sV", "--script", "vuln", t], timeout=900)


def _sweep(params):
    g = _guard()
    if g:
        return g
    t = _target(params)
    if not t:
        return _usage("sweep")
    print(f"Ping sweep of {t}...")
    return run(["nmap", "-sn", t], timeout=300)


_TARGET_PATTERN = r"(\S+)\s*$"
_PARAMS = {"type": "OBJECT",
           "properties": {"target": {"type": "STRING",
                                     "description": "IP, CIDR range, or hostname."}}}

TOOLS = [
    {"name": "nmap_quick",
     "description": "Fast nmap scan: top 100 ports. Usage: nmap quick <target>.",
     "triggers": ["nmap quick", "quick nmap", "quick scan", "fast nmap scan"],
     "arg_patterns": {"target": _TARGET_PATTERN},
     "parameters": _PARAMS,
     "handler": _quick},
    {"name": "nmap_standard",
     "description": "nmap with version detection + default scripts. Usage: nmap standard <target>.",
     "triggers": ["nmap standard", "standard nmap", "nmap scan"],
     "arg_patterns": {"target": _TARGET_PATTERN},
     "parameters": _PARAMS,
     "handler": _standard},
    {"name": "nmap_full",
     "description": "Full nmap scan: all 65535 ports, versions, scripts. Slow. Usage: nmap full <target>.",
     "triggers": ["nmap full", "full nmap", "full port scan",
                  "scan all ports"],
     "arg_patterns": {"target": _TARGET_PATTERN},
     "parameters": _PARAMS,
     "handler": _full},
    {"name": "nmap_os",
     "description": "nmap OS detection (needs sudo). Usage: nmap os <target>.",
     "triggers": ["nmap os", "os detection", "detect os",
                  "nmap operating system"],
     "arg_patterns": {"target": _TARGET_PATTERN},
     "parameters": _PARAMS,
     "handler": _os},
    {"name": "nmap_udp",
     "description": "nmap UDP scan, top 100 ports (needs sudo, slow). Usage: nmap udp <target>.",
     "triggers": ["nmap udp", "udp scan"],
     "arg_patterns": {"target": _TARGET_PATTERN},
     "parameters": _PARAMS,
     "handler": _udp},
    {"name": "nmap_vuln",
     "description": "nmap vulnerability script scan. Usage: nmap vuln <target>.",
     "triggers": ["nmap vuln", "vuln scan", "vulnerability scan"],
     "arg_patterns": {"target": _TARGET_PATTERN},
     "parameters": _PARAMS,
     "handler": _vuln},
    {"name": "nmap_sweep",
     "description": "nmap ping sweep: find live hosts. Usage: nmap sweep <subnet>.",
     "triggers": ["nmap sweep", "nmap ping sweep", "ping sweep",
                  "find live hosts", "host discovery"],
     "arg_patterns": {"target": _TARGET_PATTERN},
     "parameters": _PARAMS,
     "handler": _sweep},
]
