"""Personality commands — greetings, jokes, screen clearing (Windows build)."""
import datetime
import random


def _greeting():
    hour = datetime.datetime.now().hour
    part = ("morning" if hour < 12 else "afternoon" if hour < 17
            else "evening")
    return f"Good {part}. All systems nominal."


def _joke():
    jokes = [
        "There are only 10 kinds of people: those who understand binary and those who don't.",
        "Why do programmers prefer dark mode? Because light attracts bugs.",
        "I told my old Kali VM a UDP joke... I'm not sure it got it.",
        "A SQL query walks into a bar, sees two tables and asks... 'Mind if I join you?'",
    ]
    return random.choice(jokes)


def _clear():
    print("\033c", end="")  # ANSI reset — works on Windows 10+ terminals
    return ""


TOOLS = [
    {"name": "greeting",
     "description": "Greet the user.",
     "triggers": ["hello", "hi", "hey", "good morning", "good afternoon",
                  "good evening", "namaste"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _greeting},
    {"name": "joke",
     "description": "Tell a nerdy joke.",
     "triggers": ["joke", "tell me a joke", "make me laugh"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _joke},
    {"name": "clear",
     "description": "Clear the terminal screen.",
     "triggers": ["clear", "clear screen"],
     "parameters": {"type": "OBJECT", "properties": {}},
     "handler": _clear},
]
