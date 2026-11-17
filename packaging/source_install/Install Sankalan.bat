@echo off
REM Installs Sankalan to run from source with Python 3.13. DEVELOPMENT AND TEST FALLBACK ONLY: Smart App Control
REM blocks the unsigned duckdb and python-calamine files, so use it only where Smart App Control is off.
REM No admin rights needed. Uses the bundled "wheels" folder if present (no internet); otherwise downloads packages.
setlocal
title Install Sankalan
cd /d "%~dp0"
set "DEST=%LOCALAPPDATA%\Programs\Sankalan"
echo Installing Sankalan into %DEST%
echo.

py -3.13 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.13 64-bit is needed first.
  echo Install it from python.org with "Add python.exe to PATH" ticked, then run this installer again.
  goto :fail
)
if exist "%DEST%\Sankalan.exe" (
  echo Sankalan is already installed here with the signed installer. Uninstall it first.
  goto :fail
)

echo [1/5] Copying the app
robocopy "%~dp0app" "%DEST%\app" /MIR /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :fail

echo [2/5] Creating the Python environment
if not exist "%DEST%\venv\Scripts\pythonw.exe" (
  py -3.13 -m venv "%DEST%\venv" || goto :fail
)

echo [3/5] Installing packages
if exist "%~dp0wheels\" (
  "%DEST%\venv\Scripts\python.exe" -m pip install --disable-pip-version-check --no-index --find-links "%~dp0wheels" -r "%DEST%\app\requirements.txt" || goto :fail
) else (
  "%DEST%\venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "%DEST%\app\requirements.txt" || goto :fail
)

echo [4/5] Checking the app (self-test; a window may flash briefly)
if exist "%DEST%\selftest.json" del "%DEST%\selftest.json"
"%DEST%\venv\Scripts\python.exe" "%DEST%\app\Sankalan.pyw" --self-test --report "%DEST%\selftest.json"
findstr /c:"\"result\": \"PASS\"" "%DEST%\selftest.json" >nul 2>&1
if errorlevel 1 (
  echo Self-test failed. Details: %DEST%\selftest.json
  goto :fail
)
echo Self-test passed.

echo [5/5] Creating Start menu and desktop shortcuts
"%DEST%\venv\Scripts\python.exe" "%DEST%\app\shortcuts.py" --dest "%DEST%" || goto :fail

echo.
echo Sankalan is installed. Open it from the Start menu or the desktop shortcut.
pause
exit /b 0

:fail
echo.
echo Installation did not finish.
pause
exit /b 1
