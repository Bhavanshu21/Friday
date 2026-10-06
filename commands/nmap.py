"""
nmap scan profiles. Each is a pre-approved scan shape with a validated
target — the user picks the profile, FRIDAY fills in the flags.

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


def _syn(params):
    g = _guard()
    if g:
        return g
    t = _target(params)
    if not t:
        return _usage("syn")
    print(f"SYN stealth scan of {t} (top 1000 ports, needs sudo)...")
    return run(["sudo", "nmap", "-sS", t], timeout=300)


def _connect(params):
    g = _guard()
    if g:
        return g
    t = _target(params)
    if not t:
        return _usage("connect")
    print(f"TCP connect scan of {t} (top 1000 ports, no root needed)...")
    return run(["nmap", "-sT", t], timeout=300)


def _aggressive(params):
    g = _guard()
    if g:
        return g
    t = _target(params)
    if not t:
        return _usage("aggressive")
    print(f"Aggressive scan of {t} (OS + versions + scripts + traceroute, "
          f"needs sudo). This takes a while...")
    return run(["sudo", "nmap", "-A", t], timeout=900)


def _version(params):
    g = _guard()
    if g:
        return g
    t = _target(params)
    if not t:
        return _usage("version")
    print(f"Version detection on {t} (top 1000 ports)...")
    return run(["nmap", "-sV", t], timeout=600)


def _valid_ports(p):
    if not p or len(p) > 200 or not re.match(r"^[\d,\-]+$", p):
        return False
    for part in p.split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            if not (a.isdigit() and b.isdigit() and 1 <= int(a) <= int(b) <= 65535):
                return False
        elif not (part.isdigit() and 1 <= int(part) <= 65535):
            return False
    return True


def _ports(params):
    g = _guard()
    if g:
        return g
    t = _target(params)
    if not t:
        return _usage("ports")
    p = (params.get("ports") or "").strip()
    if not _valid_ports(p):
        return ("Usage: nmap ports <target> <ports> — ports like 80,443 "
                "or 1-1000. E.g. 'nmap ports 192.168.1.5 80,443,8080'.")
    print(f"Scanning ports {p} on {t}...")
    return run(["nmap", "-p", p, t], timeout=300)


def _valid_script(s):
    return bool(s) and len(s) <= 64 and re.match(r"^[A-Za-z0-9_.\-]+$", s)


def _script(params):
    g = _guard()
    if g:
        return g
    t = _target(params)
    if not t:
        return _usage("script")
    s = (params.get("script") or "").strip()
    if not _valid_script(s):
        return ("Usage: nmap script <target> <script> — e.g. "
                "'nmap script 192.168.1.5 http-title'.")
    print(f"Running NSE script '{s}' against {t}...")
    return run(["nmap", "--script", s, t], timeout=600)


def _list(params):
    g = _guard()
    if g:
        return g
    t = _target(params)
    if not t:
        return _usage("list")
    print(f"List scan of {t} (DNS enumeration, no packets sent)...")
    return run(["nmap", "-sL", t], timeout=120)


_TARGET_PATTERN = r"(\S+)\s*$"
_PARAMS = {"type": "OBJECT",
           "properties": {"target": {"type": "STRING",
                                     "description": "IP, CIDR range, or hostname."}}}
_PORTS_PARAMS = {"type": "OBJECT",
                 "properties": {"target": {"type": "STRING",
                                           "description": "IP, CIDR range, or hostname."},
                                "ports": {"type": "STRING",
                                          "description": "Port list like 80,443 or 1-1000."}}}
_SCRIPT_PARAMS = {"type": "OBJECT",
                  "properties": {"target": {"type": "STRING",
                                            "description": "IP, CIDR range, or hostname."},
                                 "script": {"type": "STRING",
                                            "description": "NSE script name, e.g. http-title."}}}

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
    {"name": "nmap_syn",
     "description": "nmap SYN stealth scan, top 1000 ports (needs sudo). Usage: nmap syn <target>.",
     "triggers": ["nmap syn", "syn scan", "stealth scan", "syn stealth"],
     "arg_patterns": {"target": _TARGET_PATTERN},
     "parameters": _PARAMS,
     "handler": _syn},
    {"name": "nmap_connect",
     "description": "nmap TCP connect scan, top 1000 ports (no root needed). Usage: nmap connect <target>.",
     "triggers": ["nmap connect", "connect scan", "tcp connect scan"],
     "arg_patterns": {"target": _TARGET_PATTERN},
     "parameters": _PARAMS,
     "handler": _connect},
    {"name": "nmap_aggressive",
     "description": "nmap aggressive scan: OS + versions + scripts + traceroute (needs sudo). Usage: nmap aggressive <target>.",
     "triggers": ["nmap aggressive", "aggressive scan", "aggressive nmap"],
     "arg_patterns": {"target": _TARGET_PATTERN},
     "parameters": _PARAMS,
     "handler": _aggressive},
    {"name": "nmap_version",
     "description": "nmap version detection only, top 1000 ports. Usage: nmap version <target>.",
     "triggers": ["nmap version", "version scan", "detect versions",
                  "service version scan"],
     "arg_patterns": {"target": _TARGET_PATTERN},
     "parameters": _PARAMS,
     "handler": _version},
    {"name": "nmap_ports",
     "description": "nmap scan of specific ports. Usage: nmap ports <target> <ports> (e.g. 80,443 or 1-1000).",
     "triggers": ["nmap ports", "scan specific ports", "custom port scan",
                  "scan these ports"],
     "arg_patterns": {"target": r"ports\s+(\S+)",
                      "ports": _TARGET_PATTERN},
     "parameters": _PORTS_PARAMS,
     "handler": _ports},
    {"name": "nmap_script",
     "description": "nmap with a specific NSE script. Usage: nmap script <target> <script> (e.g. http-title).",
     "triggers": ["nmap script", "nse script", "run nmap script"],
     "arg_patterns": {"target": r"script\s+(\S+)",
                      "script": _TARGET_PATTERN},
     "parameters": _SCRIPT_PARAMS,
     "handler": _script},
    {"name": "nmap_list",
     "description": "nmap list scan: DNS enumerate targets without scanning. Usage: nmap list <target>.",
     "triggers": ["nmap list", "list scan", "dns enumerate"],
     "arg_patterns": {"target": _TARGET_PATTERN},
     "parameters": _PARAMS,
     "handler": _list},
]
