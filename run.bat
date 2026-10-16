@echo off
rem EVREN Studio baslatici
setlocal
set ROOT=%~dp0
if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo Sanal ortam bulunamadi. Kurulum icin docs\INSTALLATION.md dosyasina bakin:
  echo   python -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  echo   .venv\Scripts\python.exe -m pip install -e .
  pause
  exit /b 1
)
start "" "%ROOT%.venv\Scripts\pythonw.exe" -m evren_studio
endlocal
