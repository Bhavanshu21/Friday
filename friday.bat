@echo off
rem FRIDAY launcher for Windows — mirrors the `friday` bash script.
rem Bare run = voice + Ollama brain; explicit flags override.
rem Uses the py launcher when available, falls back to python.

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%~dp0friday.py" --voice --brain ollama %*
) else (
    python "%~dp0friday.py" --voice --brain ollama %*
)
