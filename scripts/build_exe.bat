@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM SitAlarm one-click Windows EXE build (PyInstaller)
REM Usage: double-click this .bat, or run from cmd.

set "ROOT=%~dp0.."
pushd "%ROOT%" || exit /b 1

set "VENV_DIR=.venv-win"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "INDEX_URL=http://mirrors.aliyun.com/pypi/simple"
set "TRUSTED_HOST=mirrors.aliyun.com"
set "PY_VER=3.8"

echo [0/6] Cleaning previous build outputs...
taskkill /IM SitAlarm.exe /F >nul 2>nul
if exist "build" rmdir /S /Q "build"
if exist "dist" rmdir /S /Q "dist"
if exist "SitAlarm.spec" del /F /Q "SitAlarm.spec"

REM If EXE is still locked by another process, stop early to avoid stale icon/output.
if exist "dist\SitAlarm.exe" (
  echo ERROR: dist\SitAlarm.exe is still in use. Please close SitAlarm and try again.
  goto :fail
)

echo [1/6] Checking Python...
set "USE_PY_LAUNCHER=0"

py -%PY_VER% -c "import sys" >nul 2>nul
if not errorlevel 1 (
  set "USE_PY_LAUNCHER=1"
) else (
  python -c "import sys" >nul 2>nul
  if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.8+ ^(python.org^) or ensure the 'py' launcher exists.
    goto :fail
  )
)

echo [2/6] Creating venv if missing...
if not exist "%VENV_PY%" (
  if "%USE_PY_LAUNCHER%"=="1" (
    py -%PY_VER% -m venv "%VENV_DIR%" || goto :fail
  ) else (
    python -m venv "%VENV_DIR%" || goto :fail
  )
)

echo [3/6] Installing build dependencies ^(may take a while^) ...
"%VENV_PY%" -m pip install -U pip -i "%INDEX_URL%" --trusted-host "%TRUSTED_HOST%" || goto :fail
"%VENV_PY%" -m pip install -r requirements-win-build.txt -i "%INDEX_URL%" --trusted-host "%TRUSTED_HOST%" || goto :fail

REM EXE icon: Windows requires .ico, so we convert logo.png -> installer\icon.ico each build.
echo [4/6] Preparing icon from logo.png...
"%VENV_PY%" -m pip install pillow -i "%INDEX_URL%" --trusted-host "%TRUSTED_HOST%" || goto :fail
"%VENV_PY%" scripts\make_ico.py logo.png installer\icon.ico || goto :fail

echo [5/6] Building EXE with PyInstaller...
"%VENV_PY%" -m PyInstaller --noconfirm --clean --windowed --onefile --name SitAlarm --icon installer\icon.ico --add-data "logo.png;." --add-data "sitalarm/assets;sitalarm/assets" --collect-all mediapipe main.py || goto :fail

echo [6/6] Refreshing Windows icon cache...
ie4uinit.exe -ClearIconCache >nul 2>nul

if exist "dist\SitAlarm.exe" (
  echo.
  echo SUCCESS: dist\SitAlarm.exe
  set "CHECK_EXE=dist\SitAlarm-iconcheck-%RANDOM%.exe"
  copy /Y "dist\SitAlarm.exe" "!CHECK_EXE!" >nul
  echo IconCheck: !CHECK_EXE! (this new filename avoids Explorer icon cache)
  echo NOTE: If Explorer still shows old icon, press F5 or rename file once to verify.
  popd
  exit /b 0
)

echo ERROR: Build finished but dist\SitAlarm.exe was not found.

:fail
popd
exit /b 1

