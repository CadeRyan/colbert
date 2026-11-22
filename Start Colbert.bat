@echo off
rem Windows: double-click this file to start Colbert.
rem If Windows SmartScreen warns about it, choose "More info", then "Run anyway".
setlocal EnableExtensions
cd /d "%~dp0"
title Colbert
echo == Colbert ==

rem ---------------------------------------------------------------- Python 3.8+
set "PY="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>nul && set "PY=python"
if not defined PY (
  echo Colbert needs Python 3.8 or newer. Opening the download page now.
  echo Install it, tick "Add python.exe to PATH" on the first screen, then double-click this file again.
  start "" https://www.python.org/downloads/
  goto :fail
)

rem ---------------------------------------------------------------- updates (clean git checkouts only)
if not defined COLBERT_NO_UPDATE if exist ".git" (
  where git >nul 2>nul && (
    git diff --quiet HEAD >nul 2>nul && (
      echo Checking for updates...
      set GIT_TERMINAL_PROMPT=0
      git pull --ff-only --quiet >nul 2>nul || echo   ^(couldn't check; carrying on with this version^)
    )
  )
)

rem ---------------------------------------------------------------- engine
set "MSYS=C:\msys64"
if exist "%MSYS%\usr\bin\bash.exe" if exist "Makefile" (
  if not exist "app\engine\colbert.exe" (
    echo First run: the engine has to be built on this computer with MSYS2 ^(a few minutes^).
    choice /M "Build it now"
    if errorlevel 2 goto :checkengine
  )
  echo Building the engine if anything changed...
  set "MSYSTEM=UCRT64"
  set "CHERE_INVOKING=1"
  "%MSYS%\usr\bin\bash.exe" -lc "./tools/build-windows.sh" > build.log 2>&1 || echo   The build reported problems; details are in build.log.
)
:checkengine
if not exist "app\engine\colbert.exe" if not exist "app\engine\colbert-cpu.exe" (
  echo.
  echo No Windows engine was found in app\engine.
  echo To build one, install MSYS2 from https://www.msys2.org ^(keep the default folder C:\msys64^),
  echo then double-click this file again. See docs\APP.md for other options.
  start "" https://www.msys2.org/
  goto :fail
)

rem ---------------------------------------------------------------- the app
echo.
echo Starting Colbert. It opens in your web browser.
echo Keep this window open while Colbert works. Closing it saves progress and stops.
echo.
%PY% app\run.py %*
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
pause
exit /b 1
