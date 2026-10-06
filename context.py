"""
JARVIS Phase 2a — short-term conversation memory.

Keeps the last N command runs (command name, raw input, extracted params,
result text) so the assistant can do "again" (re-run) and "recall"
(find things like the last IP address it printed).

In-memory only — nothing is persisted to disk yet. Cross-session memory
is a Phase 3 concern.
"""
import re

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


class RunContext:
    def __init__(self, maxlen=10):
        self._runs = []
        self._maxlen = maxlen

    def push(self, name, raw, params, result):
        self._runs.append({
            "command": name,
            "input": raw,
            "params": dict(params or {}),
            "result": result or "",
        })
        del self._runs[:-self._maxlen]

    def last(self):
        return self._runs[-1] if self._runs else None

    def find_ip(self):
        """Most recent IPv4 address seen in any stored result."""
        for run in reversed(self._runs):
            m = _IP_RE.search(run["result"])
            if m:
                return m.group(0)
        return None
