"""System introspection + control commands."""
import datetime
import re
from common import run, need, get_user

# tail is restricted to these logs by design — the command defines its own
# allowlist, so no path traversal is possible.
LOGS = {
    "auth": "/var/log/auth.log",
    "syslog": "/var/log/syslog",
    "kern": "/var/log/kern.log",
    "boot": "/var/log/boot.log",
}

_SERVICE_RE = re.compile(r"^[A-Za-z0-9@.\-]{1,64}$")
_SERVICE_ACTIONS = ("status", "start", "stop", "restart")


def _status():
    up = run(["uptime", "-p"])
    load = run(["cat", "/proc/loadavg"]).split()[:3]
    mem = run(["free", "-h"]).splitlines()
    disk = run(["df", "-h", "/"]).splitlines()
    mem_line = mem[1] if len(mem) > 1 else ""
    disk_line = disk[1] if len(disk) > 1 else ""
    return (f"Uptime: {up}\n"
            f"Load: {' '.join(load)}\n"
            f"Memory: {mem_line}\n"
            f"Disk:   {disk_line}")


def _disk():
    return run(["df", "-h"])


def _memory():
    return run(["free", "-h"])


def _uptime():
    return run(["uptime", "-p"])


def _kernel():
    return run(["uname", "-r"])


def _date():
    return datetime.datetime.now().strftime("%A, %d %B %Y — %H:%M:%S")


def _whoami():
    return get_user()


def _reboot():
    ans = input("Reboot the VM now? Type YES to confirm: ").strip()
    if ans == "YES":
        from common import log
        log("reboot (confirmed)")
        import subprocess
        subprocess.run(["sudo", "reboot"])
        return "Rebooting..."
    return "Reboot cancelled. Smart choice."


def _tail(params):
    logname = (params.get("log") or "").strip().lower()
    lines = (params.get("lines") or "20").strip()
    if logname not in LOGS:
        return ("Usage: tail <log> [lines]  — logs: "
                + ", ".join(sorted(LOGS)) + ".")
    n = lines if lines.isdigit() and 1 <= int(lines) <= 200 else "20"
    return run(["tail", "-n", n, LOGS[logname]], timeout=30)


def _service(params):
    name = (params.get("name") or "").strip()
    action = (params.get("action") or "status").strip().lower()
    if not _SERVICE_RE.match(name) or action not in _SERVICE_ACTIONS:
        return ("Usage: service <name> <status|start|stop|restart>  — "
                "e.g. 'service ssh status'.")
    if not need("systemctl"):
        return "systemctl isn't available."
    return run(["sudo", "systemctl", action, name], timeout=60)


TOOLS = [
    {"name": "status",
     "description": "Show system status: uptime, load average, memory and disk usage.",
     "triggers": ["status", "system status", "health", "how are you"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _status},
    {"name": "disk",
     "description": "Show disk usage for all mounted filesystems.",
     "triggers": ["disk", "disk usage", "disk space", "storage"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _disk},
    {"name": "memory",
     "description": "Show memory (RAM) usage.",
     "triggers": ["memory", "ram", "memory usage"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _memory},
    {"name": "uptime",
     "description": "Show how long the system has been running.",
     "triggers": ["uptime", "how long running", "boot time"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _uptime},
    {"name": "kernel",
     "description": "Show the kernel version.",
     "triggers": ["kernel", "kernel version", "os version"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _kernel},
    {"name": "date",
     "description": "Show the current date and time.",
     "triggers": ["date", "time", "what time", "what's the time",
                  "current time"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _date},
    {"name": "whoami",
     "description": "Show the current username.",
     "triggers": ["whoami", "who am i", "current user", "username"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _whoami},
    {"name": "reboot",
     "description": "Reboot the machine. Asks for typed YES confirmation first.",
     "triggers": ["reboot", "restart", "restart system"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _reboot},
    {"name": "tail",
     "description": "Show the last lines of a system log. Usage: tail <auth|syslog|kern|boot> [lines].",
     "triggers": ["tail", "show log", "view log", "check log",
                  "auth log", "syslog", "kern log", "boot log"],
     "arg_patterns": {"log": r"\b(auth|syslog|kern|boot)\b",
                      "lines": r"\b(?:auth|syslog|kern|boot)\b(?:\s+log)?\s+(\d+)"},
     "parameters": {"type": "OBJECT",
                    "properties": {"log": {"type": "STRING",
                                           "description": "Which log: auth, syslog, kern, boot."},
                                   "lines": {"type": "STRING",
                                             "description": "How many lines (default 20, max 200)."}}},
     "handler": _tail},
    {"name": "service",
     "description": "Control a systemd service. Usage: service <name> <status|start|stop|restart>.",
     "triggers": ["service"],
     "arg_patterns": {"name": r"service\s+([A-Za-z0-9@.\-]+)",
                      "action": r"service\s+[A-Za-z0-9@.\-]+\s+([a-z]+)"},
     "parameters": {"type": "OBJECT",
                    "properties": {"name": {"type": "STRING",
                                            "description": "Service name, e.g. ssh."},
                                   "action": {"type": "STRING",
                                              "description": "status, start, stop or restart."}}},
     "handler": _service},
]
