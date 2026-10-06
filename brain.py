"""
JARVIS Phase 3 — the brain. A local Ollama LLM picks tools from the registry.

Uses Ollama's native /api/chat `tools` parameter (think: false — no reasoning
overhead for tool dispatch). The model may ONLY return a registered tool
name; anything else is rejected before execution. The registry remains the
allowlist — the brain never invents commands.

Stdlib only (urllib). Default model: qwen3:4b.

SAFETY NOTE (prompt injection): tool outputs are NEVER fed back into the
model. Conversation history records intents ("ran nmap_quick"), not raw
outputs — hostile text in a log or scan result can't steer the next
decision. The existing per-command argument validation still applies.
"""
import json
import urllib.request
import urllib.error

DEFAULT_MODEL = "qwen3:4b"
DEFAULT_URL = "http://localhost:11434"

SYSTEM_PROMPT = (
    "You are JARVIS, a personal assistant running on the user's own Kali "
    "Linux virtual machine. You act ONLY through the provided tools.\n"
    "Rules:\n"
    "- To do something, call exactly one tool per response, with its arguments.\n"
    "- If no tool fits the request, answer directly in one or two sentences.\n"
    "- Never invent tool names, and never add parameters a tool does not define.\n"
    "- Keep chit-chat short. You are direct and technical."
)

# Mark-LV-style UPPERCASE schema types -> JSON-schema lowercase for Ollama.
_TYPE_FIX = {"OBJECT": "object", "STRING": "string", "NUMBER": "number",
             "INTEGER": "integer", "BOOLEAN": "boolean", "ARRAY": "array"}


def _fix_schema(node):
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k == "type" and isinstance(v, str):
                out[k] = _TYPE_FIX.get(v, v)
            else:
                out[k] = _fix_schema(v)
        return out
    if isinstance(node, list):
        return [_fix_schema(i) for i in node]
    return node


def registry_to_tools(registry):
    """Registry -> Ollama tools list. One entry per command."""
    tools = []
    for cmd in registry.values():
        tools.append({
            "type": "function",
            "function": {
                "name": cmd["name"],
                "description": cmd["description"],
                "parameters": _fix_schema(cmd.get("parameters") or
                                          {"type": "object", "properties": {}}),
            },
        })
    return tools


class Brain:
    def __init__(self, model=DEFAULT_MODEL, base_url=DEFAULT_URL,
                 timeout=120):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------ setup
    def _get(self, path):
        req = urllib.request.Request(self.base_url + path, method="GET")
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())

    def _post(self, path, payload):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.base_url + path, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode())

    def available(self):
        """
        Returns (True, "") if Ollama is up AND the model is present,
        else (False, reason).
        """
        try:
            tags = self._get("/api/tags")
        except Exception:
            return False, ("Ollama isn't reachable at " + self.base_url +
                           ". Start it with:  ollama serve")
        models = [m.get("name", "") for m in tags.get("models", [])]
        if not any(m == self.model or m.startswith(self.model + ":")
                   for m in models):
            return False, (f"model '{self.model}' isn't pulled yet. " +
                           f"Run:  ollama pull {self.model}")
        return True, ""

    # ------------------------------------------------------------------ choose
    def choose(self, user_text, registry, history):
        """
        Ask the model. Returns one of:
          ("tool", name, args)   — run registry[name] with args
          ("chat", text)         — plain reply, no tool
          ("unavailable", None)  — Ollama unreachable; caller falls back
        history: list of {"role", "content"} (intents only, never outputs).
        """
        tools = registry_to_tools(registry)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += history[-6:]
        messages.append({"role": "user", "content": user_text})
        payload = {"model": self.model, "messages": messages, "tools": tools,
                   "think": False, "stream": False,
                   "options": {"temperature": 0.7, "top_p": 0.8,
                               "top_k": 20, "num_ctx": 8192}}
        try:
            resp = self._post("/api/chat", payload)
        except Exception:
            return ("unavailable", None)

        msg = resp.get("message", {}) or {}
        calls = msg.get("tool_calls") or []
        if calls:
            fn = (calls[0].get("function") or {})
            name = fn.get("name", "")
            args = fn.get("arguments") or {}
            if name in registry and isinstance(args, dict):
                return ("tool", name, args)
            return ("chat", f"I reached for an unknown tool ({name!r}) — "
                            "refusing to run it.")
        content = (msg.get("content") or "").strip()
        return ("chat", content if content else "...")
