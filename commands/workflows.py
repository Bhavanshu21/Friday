"""
Composite workflows — commands that run other registered commands and
combine the results. They receive ctx = {"registry", "context"} from the
dispatcher and call sibling handlers directly (no subprocess, no shell).
"""
import inspect


def _call(cmd, ctx):
    """Invoke another registered command's handler, honoring its signature."""
    sig = inspect.signature(cmd["handler"])
    kwargs = {}
    if "params" in sig.parameters:
        kwargs["params"] = {}
    if "ctx" in sig.parameters:
        kwargs["ctx"] = ctx
    try:
        return cmd["handler"](**kwargs) or "(no output)"
    except Exception as e:
        return f"(failed: {e})"


def _health(ctx):
    reg = ctx["registry"]
    out = ["SYSTEM HEALTH CHECK", ""]
    for label, name in (("status", "status"), ("disk", "disk"),
                        ("memory", "memory"), ("updates", "packages")):
        cmd = reg.get(name)
        out.append(f"--- {label} ---")
        out.append(_call(cmd, ctx) if cmd else "(not loaded)")
        out.append("")
    return "\n".join(out).strip()


TOOLS = [
    {"name": "health_check",
     "description": "Full system health check: status, disk, memory and pending updates in one report.",
     "triggers": ["health check", "system health", "full checkup",
                  "checkup", "health report"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _health},
]
