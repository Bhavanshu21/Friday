"""
Command auto-discovery — the Mark-LV pattern, adapted for FRIDAY.

A command file is any commands/*.py (no leading underscore) exposing either:
    TOOL  = {...}        # a single command
    TOOLS = [{...}, ...] # several commands in one file

Each TOOL dict:
    {
        "name":        "wifi",                  # unique identifier
        "description": "Scan for nearby Wi-Fi networks (read-only).",
                                               # Phase 3: the LLM reads this
        "triggers":    ["wifi", "scan wifi"],   # Phase 1: the keyword matcher reads these
        "parameters":  {"type": "OBJECT", "properties": {}},
                                               # Phase 3: LLM function-calling schema
        "handler":     callable,                # runs it; returns a string
    }

Why both description AND triggers? Phase 1 matches keywords (triggers).
Phase 3 will hand name+description+parameters to a local LLM for function
calling. The registry serves both brains — the day the matcher is swapped,
no command file changes.

Files that fail to import, fail validation, or collide on names are logged
and skipped. They NEVER abort discovery of the rest.
"""
import importlib.util
import re
import sys
import traceback
from pathlib import Path

_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")


def _validate(tool, filename):
    """Returns (record, error). error is '' when valid."""
    if not isinstance(tool, dict):
        return None, "not a dict"
    name = tool.get("name")
    if not isinstance(name, str) or not _NAME_RE.match(name):
        return None, f"bad name {name!r}"
    desc = tool.get("description")
    if not isinstance(desc, str) or not desc.strip():
        return None, f"{name}: empty description"
    triggers = tool.get("triggers")
    if (not isinstance(triggers, list) or not triggers
            or not all(isinstance(t, str) and t.strip() for t in triggers)):
        return None, f"{name}: triggers must be a non-empty list of strings"
    params = tool.get("parameters", {"type": "OBJECT", "properties": {}})
    if not isinstance(params, dict) or params.get("type") != "OBJECT":
        return None, f"{name}: parameters must be a dict with type OBJECT"
    handler = tool.get("handler")
    if not callable(handler):
        return None, f"{name}: handler not callable"
    arg_patterns = tool.get("arg_patterns", {})
    if (not isinstance(arg_patterns, dict)
            or not all(isinstance(k, str) and isinstance(v, str)
                       for k, v in arg_patterns.items())):
        return None, f"{name}: arg_patterns must be a dict of name -> regex"
    for pat in arg_patterns.values():
        try:
            re.compile(pat)
        except re.error:
            return None, f"{name}: bad regex in arg_patterns: {pat!r}"
    return {"name": name, "description": desc.strip(), "triggers": triggers,
            "parameters": params, "handler": handler, "file": filename,
            "arg_patterns": arg_patterns}, ""


def discover_commands(commands_dir):
    """
    Scan commands_dir. Returns (registry, report).
    registry: name -> record. report: list of (file, ok, message).
    """
    commands_dir = Path(commands_dir)
    commands_dir.mkdir(parents=True, exist_ok=True)
    registry, report = {}, []
    for path in sorted(commands_dir.glob("*.py"), key=lambda p: p.name):
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        try:
            mod_name = f"commands.{path.stem}"
            module = sys.modules.get(mod_name)
            if module is None:
                spec = importlib.util.spec_from_file_location(mod_name, path)
                if spec is None or spec.loader is None:
                    raise ImportError("could not build import spec")
                module = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = module
                try:
                    spec.loader.exec_module(module)
                except Exception:
                    sys.modules.pop(mod_name, None)
                    raise
            tools = []
            if isinstance(getattr(module, "TOOLS", None), list):
                tools = module.TOOLS
            elif isinstance(getattr(module, "TOOL", None), dict):
                tools = [module.TOOL]
            else:
                continue  # helper file, not a command file — silently skip
            for tool in tools:
                rec, err = _validate(tool, path.name)
                if err:
                    report.append((path.name, False, err))
                elif rec["name"] in registry:
                    report.append((path.name, False,
                                   f"name '{rec['name']}' already registered"))
                else:
                    registry[rec["name"]] = rec
                    report.append((path.name, True,
                                   f"loaded '{rec['name']}'"))
        except Exception as e:
            traceback.print_exc()
            report.append((path.name, False, f"import failed: {e}"))
    return registry, report
