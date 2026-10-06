"""Package management and hardware commands."""
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
]
