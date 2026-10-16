@echo off
rem EVREN Model Studio basit başlatıcı
setlocal
set ROOT=%~dp0
"%ROOT%.venv\Scripts\python.exe" -m evren_studio
if errorlevel 1 (
  echo.
  echo Uygulama beklenmedik şekilde kapandi. logs klasorunu inceleyin.
  pause
)
endlocal
