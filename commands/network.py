"""Network commands — diagnostics. Parameterized ones validate their target."""
import re
from common import run, need

_HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.\-]*[A-Za-z0-9])?$")


def _valid_host(h):
    return bool(h) and bool(_HOST_RE.match(h)) and len(h) <= 253


def _ip():
    return run(["hostname", "-I"])


def _internet():
    out = run(["ping", "-c", "2", "-W", "3", "8.8.8.8"], timeout=20)
    if "0% packet loss" in out or "0% loss" in out:
        return "Uplink is live. We're online."
    if "100% packet loss" in out or "100% loss" in out:
        return "No route to the internet. Check the VM's NAT adapter."
    return out


def _ports():
    if not need("ss"):
        return "The 'ss' tool isn't installed."
    return run(["ss", "-tln"])


def _processes():
    return run(["ps", "aux", "--sort=-%cpu"])


def _wifi():
    if not need("nmcli"):
        return "nmcli isn't installed."
    print("Scanning the airwaves...")
    return run(["nmcli", "dev", "wifi", "list"], timeout=30)


def _ping(params):
    host = (params.get("host") or "").strip()
    if not _valid_host(host):
        return "Usage: ping <host>  — e.g. 'ping 8.8.8.8'."
    return run(["ping", "-c", "4", "-W", "3", host], timeout=30)


def _traceroute(params):
    host = (params.get("host") or "").strip()
    if not _valid_host(host):
        return "Usage: traceroute <host>  — e.g. 'traceroute 8.8.8.8'."
    if not need("traceroute"):
        return "The 'traceroute' tool isn't installed."
    print(f"Tracing route to {host} (max 20 hops)...")
    return run(["traceroute", "-m", "20", host], timeout=120)


def _lookup(params):
    domain = (params.get("domain") or "").strip()
    if not _valid_host(domain):
        return "Usage: lookup <domain>  — e.g. 'lookup example.com'."
    if not need("dig"):
        return "The 'dig' tool isn't installed."
    return run(["dig", "+short", domain], timeout=20)


def _internet():
    out = run(["ping", "-c", "2", "-W", "3", "8.8.8.8"], timeout=20)
    if "0% packet loss" in out or "0% loss" in out:
        return "Uplink is live. We're online."
    if "100% packet loss" in out or "100% loss" in out:
        return "No route to the internet. Check the VM's NAT adapter."
    return out


def _ports():
    if not need("ss"):
        return "The 'ss' tool isn't installed."
    return run(["ss", "-tln"])


def _processes():
    return run(["ps", "aux", "--sort=-%cpu"])


def _wifi():
    if not need("nmcli"):
        return "nmcli isn't installed."
    print("Scanning the airwaves...")
    return run(["nmcli", "dev", "wifi", "list"], timeout=30)


TOOLS = [
    {"name": "ip",
     "description": "Show the machine's IP addresses.",
     "triggers": ["ip", "ip address", "what's my ip", "what is my ip",
                  "my ip", "network address"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _ip},
    {"name": "internet",
     "description": "Check internet connectivity by pinging 8.8.8.8.",
     "triggers": ["internet", "online", "check internet",
                  "am i online", "connectivity"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _internet},
    {"name": "ports",
     "description": "Show listening TCP network ports.",
     "triggers": ["ports", "listening ports", "open ports"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _ports},
    {"name": "processes",
     "description": "Show processes sorted by CPU usage.",
     "triggers": ["processes", "top processes", "cpu usage",
                  "what's running"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _processes},
    {"name": "wifi",
     "description": "Scan for nearby Wi-Fi networks. Read-only.",
     "triggers": ["wifi", "wi-fi", "scan wifi", "wireless networks",
                  "nearby networks"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _wifi},
    {"name": "ping",
     "description": "Ping a host 4 times. Usage: ping <host>.",
     "triggers": ["ping"],
     "arg_patterns": {"host": r"ping\s+([A-Za-z0-9.\-]+)"},
     "parameters": {"type": "OBJECT",
                    "properties": {"host": {"type": "STRING",
                                            "description": "Host or IP to ping."}}},
     "handler": _ping},
    {"name": "traceroute",
     "description": "Trace the network route to a host. Usage: traceroute <host>.",
     "triggers": ["traceroute", "trace route", "tracert"],
     "arg_patterns": {"host": r"(?:traceroute|trace route|tracert)\s+([A-Za-z0-9.\-]+)"},
     "parameters": {"type": "OBJECT",
                    "properties": {"host": {"type": "STRING",
                                            "description": "Host or IP to trace."}}},
     "handler": _traceroute},
    {"name": "lookup",
     "description": "DNS lookup for a domain. Usage: lookup <domain>.",
     "triggers": ["lookup", "dns lookup", "nslookup", "resolve"],
     "arg_patterns": {"domain": r"(?:lookup|dns lookup|nslookup|resolve)\s+([A-Za-z0-9.\-]+)"},
     "parameters": {"type": "OBJECT",
                    "properties": {"domain": {"type": "STRING",
                                               "description": "Domain to resolve."}}},
     "handler": _lookup},
]
