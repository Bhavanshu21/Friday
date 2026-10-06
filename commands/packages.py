"""Package management and hardware commands."""
import sys
from pathlib import Path
from common import run, need, log


def _update():
    if not need("apt"):
        return "apt isn't available here."
    print("On it — this may take a while. (sudo will ask for your password)")
    log("apt update")
    run(["sudo", "apt", "update"], timeout=300)
    log("apt upgrade -y")
    out = run(["sudo", "apt", "upgrade", "-y"], timeout=1800)
    tail = "\n".join(out.splitlines()[-8:])
    return f"Update finished.\n--- tail of upgrade ---\n{tail}"


def _packages():
    if not need("apt"):
        return "apt isn't available here."
    out = run(["apt", "list", "--upgradable"], timeout=120)
    lines = [l for l in out.splitlines()
             if l and not l.startswith("Listing")]
    n = len(lines)
    if n == 0:
        return "Everything is up to date. Nothing pending."
    return f"{n} package{'s' if n != 1 else ''} can be upgraded."


def _usb():
    if not need("lsusb"):
        return "lsusb isn't installed (package: usbutils)."
    return run(["lsusb"])


def _install_requirements():
    """pip install everything FRIDAY needs (voice mode deps)."""
    req = Path(__file__).resolve().parent.parent / "requirements.txt"
    if not req.exists():
        return "requirements.txt not found next to friday.py — can't install."
    print("Installing FRIDAY requirements — this can take a few minutes...")
    log("pip install -r requirements.txt")
    argv = [sys.executable, "-m", "pip", "install", "-r", str(req)]
    out = run(argv, timeout=900)
    if out.startswith("Command failed") and "externally-managed-environment" in out:
        # Debian/Kali protect the system Python — retry with the override.
        print("System Python is protected — retrying with --break-system-packages.")
        log("pip install --break-system-packages -r requirements.txt")
        argv.insert(4, "--break-system-packages")
        out = run(argv, timeout=900)
    if out.startswith("Command failed") or "ERROR:" in out:
        return f"Install failed:\n{out}"
    tail = "\n".join(out.splitlines()[-6:])
    return f"Requirements installed.\n--- tail ---\n{tail}"


TOOLS = [
    {"name": "update",
     "description": "Run apt update and apt upgrade. May ask for the sudo password.",
     "triggers": ["update", "upgrade", "update system", "upgrade system",
                  "system update"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _update},
    {"name": "packages",
     "description": "Count how many packages have updates available.",
     "triggers": ["packages", "updates", "upgradable", "updates available",
                  "how many updates", "pending updates"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _packages},
    {"name": "usb",
     "description": "List USB devices. Useful for checking Wi-Fi adapters.",
     "triggers": ["usb", "usb devices", "list usb"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _usb},
    {"name": "install_requirements",
     "description": ("Install FRIDAY Python requirements (voice mode) via pip. "
                     "Retries with --break-system-packages on Debian/Kali."),
     "triggers": ["install requirements", "setup requirements",
                  "install dependencies", "setup dependencies",
                  "install voice", "setup voice"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _install_requirements},
]
