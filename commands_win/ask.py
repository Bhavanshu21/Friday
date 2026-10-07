"""Web Q&A for the Windows build — weather, word meanings, general questions.

Answers are synthesized into plain explanations, not raw search dumps.
All sources are free and keyless. Web content is untrusted: it is only
ever summarized for display via brain.synthesize(), never executed and
never fed back into the dispatch loop.
"""
import json
import os
import re
import urllib.parse
import urllib.request

_UA = {"User-Agent": "FRIDAY/1.0 (personal assistant)"}


def _fetch_json(url, timeout=20):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _fetch_text(url, timeout=20):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


# ------------------------------------------------------------------ weather
def _weather(params):
    place = (params.get("place") or "").strip()
    if not place:
        try:  # guess from IP, stated as a guess in the answer
            geo = _fetch_json("http://ip-api.com/json/?fields=city")
            place = (geo.get("city") or "").strip()
        except Exception:
            pass
    if not place:
        return "Which city? Say e.g. weather in Delhi."
    try:
        data = _fetch_json(
            "https://wttr.in/" + urllib.parse.quote(place) + "?format=j1")
        cur = data["current_condition"][0]
    except Exception:
        return f"Couldn't get the weather for {place}."
    desc = cur["weatherDesc"][0]["value"]
    return (f"{place}: {cur['temp_C']}°C, {desc.lower()}, "
            f"feels like {cur['FeelsLikeC']}°C. Humidity {cur['humidity']}%.")
# ------------------------------------------------------------------ define
def _define(params):
    word = re.sub(r"[^a-zA-Z\- ]", "", (params.get("word") or "")).strip().lower()
    if not word:
        return "Which word? Say e.g. define serendipity."
    try:
        data = _fetch_json("https://api.dictionaryapi.dev/api/v2/entries/en/"
                           + urllib.parse.quote(word))
        entry = data[0]
    except Exception:
        return f"No definition found for {word!r}."
    lines, n = [f"{entry.get('word', word)}:"], 0
    for meaning in entry.get("meanings", []):
        pos = meaning.get("partOfSpeech", "")
        for d in meaning.get("definitions", [])[:2]:
            n += 1
            lines.append(f"  {n}. ({pos}) {d.get('definition', '')}")
            if n >= 3:
                break
        if n >= 3:
            break
    return "\n".join(lines) if n else f"No definition found for {word!r}."
# ------------------------------------------------------------------ ask
def _wiki_summary(query):
    """Returns (title, extract) or (None, None)."""
    try:
        s = _fetch_json(
            "https://en.wikipedia.org/w/api.php?action=query&list=search"
            "&srsearch=" + urllib.parse.quote(query) + "&format=json&srlimit=3")
        results = (s.get("query") or {}).get("search", [])
        if not results:
            return None, None
        title = results[0]["title"]
        page = _fetch_json("https://en.wikipedia.org/api/rest_v1/page/summary/"
                           + urllib.parse.quote(title))
        return title, page.get("extract") or ""
    except Exception:
        return None, None


def _ddg_snippets(query, k=4):
    try:
        html = _fetch_text("https://html.duckduckgo.com/html/?q="
                           + urllib.parse.quote(query))
        snips = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.S)
        clean = [re.sub(r"<[^>]+>", "", s).strip() for s in snips]
        return [c for c in clean if c][:k]
    except Exception:
        return []


def _synthesize(question, source):
    try:
        from brain import Brain, DEFAULT_MODEL, DEFAULT_URL
    except ImportError:
        return ""
    b = Brain(model=DEFAULT_MODEL,
              base_url=os.environ.get("FRIDAY_BRAIN_URL") or DEFAULT_URL,
              timeout=120)
    ok, _ = b.available()
    return b.synthesize(question, source) if ok else ""


def _ask(params):
    q = (params.get("question") or "").strip().strip("\"'")
    if not q:
        return "Ask me what? e.g. explain photosynthesis."
    title, extract = _wiki_summary(q)
    source, label = "", ""
    if extract and len(extract) > 120:
        source, label = f"{title}: {extract}", "Wikipedia"
    else:
        snips = _ddg_snippets(q)
        if snips:
            source = "\n".join(f"- {s}" for s in snips)
            label = "web search"
    if not source:
        return f"I couldn't find anything on {q!r}."
    ans = _synthesize(q, source)
    if ans:
        return ans
    return (f"Here's what I found ({label}) — the brain isn't reachable "
            f"right now to simplify it:\n{source[:1200]}")


TOOLS = [
    {"name": "ask_weather",
     "description": "Current weather for a city, in plain words. "
                    "Usage: what's the weather in Delhi.",
     "triggers": ["weather", "temperature outside", "forecast", "will it rain"],
     "parameters": {"type": "OBJECT", "properties": {
         "place": {"type": "STRING", "description": "city name (guessed from IP if omitted)"}}},
     "arg_patterns": {"place": r"(?:weather|temperature|forecast)\s+(?:in|at|for)\s+([A-Za-z ]+)"},
     "handler": _weather},
    {"name": "ask_define",
     "description": "Plain-language meaning of an English word. "
                    "Usage: define serendipity.",
     "triggers": ["meaning of", "define", "definition of", "what does",
                  "dictionary"],
     "parameters": {"type": "OBJECT", "properties": {
         "word": {"type": "STRING", "description": "the word to define"}}},
     "arg_patterns": {"word": r"(?:meaning of|define|definition of)\s+([A-Za-z\- ]+)"},
     "handler": _define},
    {"name": "ask",
     "description": "Answer a general knowledge question by searching the web "
                    "and explaining simply. Usage: explain photosynthesis.",
     "triggers": ["what is", "what's", "who is", "explain", "tell me about",
                  "how do", "how does", "why is", "why does"],
     "parameters": {"type": "OBJECT", "properties": {
         "question": {"type": "STRING", "description": "the question to answer"}}},
     "arg_patterns": {"question": r"(?:what is|what's|who is|explain|tell me about|how do|how does|why is|why does)\s+(.+)$"},
     "handler": _ask},
]
