@echo off
cd /d "%~dp0"
where py >nul 2>nul && (py -3 friday_gui.py) || (python friday_gui.py)
if errorlevel 1 pause
