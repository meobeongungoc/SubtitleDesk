@echo off
if exist "%~dp0dist\SubtitleDesk\SubtitleDesk.exe" (
  start "" "%~dp0dist\SubtitleDesk\SubtitleDesk.exe"
) else (
  start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
)
