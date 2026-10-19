@echo off
rem EVREN Studio baslatici
setlocal
set ROOT=%~dp0
if not exist "%ROOT%.venv\Scripts\pythonw.exe" (
  echo Uygulama henuz kurulmamis; kurulum baslatiliyor...
  call "%ROOT%kurulum.bat"
  if errorlevel 1 exit /b 1
)
start "" "%ROOT%.venv\Scripts\pythonw.exe" -m evren_studio
endlocal
