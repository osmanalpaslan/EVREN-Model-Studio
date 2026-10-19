@echo off
rem EVREN Studio - tek tikla kurulum (Windows 10/11)
rem 1) Python 3.12+ bulur (yoksa izin isteyip winget ile kullanici kapsaminda kurar)
rem 2) .venv sanal ortamini olusturur, gerekli paketleri kurar
rem 3) Masaustu ve Baslat menusu kisayolu olusturur (EVREN_KURULUM_KISAYOL=0 ile atlanir)
rem Bu dosya ASCII'dir (cmd kod sayfasi sorunlarini onlemek icin Turkce harf yok).
setlocal EnableExtensions EnableDelayedExpansion
set "ROOT=%~dp0"
cd /d "%ROOT%"
echo.
echo  EVREN Studio kurulumu
echo  =====================
echo.

call :find_python
if not defined PYEXE (
  echo Python 3.12 veya ustu bulunamadi.
  where winget >nul 2>nul
  if errorlevel 1 (
    echo winget de bulunamadi. Python'u https://www.python.org/downloads/ adresinden
    echo kurup ^(kurulumda "Add python.exe to PATH" isaretli^) bu dosyayi yeniden calistirin.
    goto :fail
  )
  if /i not "%EVREN_KURULUM_EVET%"=="1" (
    set /p "CEVAP=Python 3.12 simdi winget ile kurulsun mu? (E/H): "
    if /i not "!CEVAP!"=="E" goto :fail
  )
  echo Python 3.12 kuruluyor ^(birkac dakika surebilir^)...
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  call :find_python
  if not defined PYEXE (
    echo Python kuruldu ama bulunamadi. Bilgisayari yeniden baslatip bu dosyayi tekrar calistirin.
    goto :fail
  )
)
echo Python: %PYEXE%

if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo Sanal ortam olusturuluyor...
  "%PYEXE%" -m venv "%ROOT%.venv"
  if errorlevel 1 goto :fail
)
set "VPY=%ROOT%.venv\Scripts\python.exe"
echo Paketler kuruluyor ^(ilk seferde birkac dakika surebilir^)...
"%VPY%" -m pip install --disable-pip-version-check -q --upgrade pip
"%VPY%" -m pip install --disable-pip-version-check -q -r "%ROOT%requirements.txt"
if errorlevel 1 goto :fail
"%VPY%" -m pip install --disable-pip-version-check -q -e "%ROOT%."
if errorlevel 1 goto :fail
"%VPY%" -c "import PySide6, httpx, keyring, markdown, pygments, evren_studio"
if errorlevel 1 goto :fail
echo Paketler hazir.

if not "%EVREN_KURULUM_KISAYOL%"=="0" (
  "%VPY%" "%ROOT%tools\kurulum_kisayol.py"
)
echo.
echo  Kurulum tamamlandi. Uygulamayi masaustundeki "EVREN Studio" kisayolundan
echo  veya run.bat ile acabilirsiniz. Ilk acilista EVREN API anahtarinizi girin.
echo.
if /i not "%EVREN_KURULUM_EVET%"=="1" pause
endlocal
exit /b 0

:fail
echo.
echo  KURULUM TAMAMLANAMADI. Yukaridaki mesaja bakin; sorun surerse
echo  docs\INSTALLATION.md dosyasindaki elle kurulum adimlarini izleyin.
echo.
if /i not "%EVREN_KURULUM_EVET%"=="1" pause
endlocal
exit /b 1

:find_python
rem Microsoft Store'un sahte "python" kisayolu calismaz; surum denetimiyle elenir.
set "PYEXE="
for %%P in ("%ROOT%.venv\Scripts\python.exe" "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%ProgramFiles%\Python313\python.exe" "%ProgramFiles%\Python312\python.exe") do (
  if not defined PYEXE if exist "%%~P" (
    "%%~P" -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul && set "PYEXE=%%~P"
  )
)
if defined PYEXE if /i "%PYEXE%"=="%ROOT%.venv\Scripts\python.exe" (
  rem .venv zaten var: ondan baz Python'u turet
  for /f "usebackq delims=" %%B in (`"%PYEXE%" -c "import sys; print(sys._base_executable)"`) do set "PYEXE=%%B"
)
if not defined PYEXE (
  for %%C in (py python python3) do (
    if not defined PYEXE (
      for /f "usebackq delims=" %%E in (`%%C -c "import sys; print(sys.executable if sys.version_info >= (3, 12) else '')" 2^>nul`) do (
        if not "%%E"=="" set "PYEXE=%%E"
      )
    )
  )
)
exit /b 0
