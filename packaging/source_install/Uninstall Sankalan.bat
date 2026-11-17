@echo off
REM Removes the run-from-source Sankalan (program folder and shortcuts) and asks whether to delete the data (T26).
setlocal
title Uninstall Sankalan
set "DEST=%LOCALAPPDATA%\Programs\Sankalan"
if not exist "%DEST%\app\Sankalan.pyw" (
  echo Sankalan from source is not installed in %DEST%.
  pause
  exit /b 0
)
echo This removes Sankalan from %DEST% and its shortcuts. Close Sankalan first.
choice /c YN /m "Continue"
if errorlevel 2 exit /b 0
echo.
echo Do you also want to delete your Sankalan data (all clients, templates, runs, saved analyses,
echo settings and logs)? This can't be undone. N keeps your data for a later install.
choice /c YN /n /m "Delete your data? [Y/N] "
if errorlevel 2 goto :program
"%DEST%\venv\Scripts\python.exe" "%DEST%\app\Sankalan.pyw" --remove-data
if errorlevel 2 (
  echo Your data folder was not deleted because it doesn't look like a Sankalan data folder.
) else if errorlevel 1 (
  echo Some of Sankalan's data could not be deleted. Close any program using it, then delete it yourself.
)
:program
"%DEST%\venv\Scripts\python.exe" "%DEST%\app\shortcuts.py" --dest "%DEST%" --remove
rmdir /s /q "%DEST%"
echo Sankalan has been removed.
pause
