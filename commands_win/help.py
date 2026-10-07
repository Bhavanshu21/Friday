"""Meta command: list everything FRIDAY can do, from the live registry."""


def _help(ctx):
    reg = (ctx or {}).get("registry", {})
    if not reg:
        return "No commands registered."
    lines = ["Here's what I can do:"]
    for name in sorted(reg):
        desc = (reg[name].get("description") or "").strip()
        short = desc.split(".")[0].strip()
        lines.append(f"  {name} — {short}")
    return "\n".join(lines)


TOOL = {
    "name": "help",
    "description": "List all available commands and what each does. "
                   "Usage: help / what can you do.",
    "triggers": ["help", "what can you do", "commands", "list commands",
                 "show commands"],
    "parameters": {"type": "OBJECT", "properties": {}},
    "handler": _help,
}
