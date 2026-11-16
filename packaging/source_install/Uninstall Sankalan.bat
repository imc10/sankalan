@echo off
REM Removes Sankalan's program folder and shortcuts. Templates and output files are kept.
setlocal
title Uninstall Sankalan
set "DEST=%LOCALAPPDATA%\Programs\Sankalan"
echo This removes Sankalan from %DEST% and its shortcuts.
echo Your templates in Documents\Sankalan\Templates are kept.
choice /c YN /m "Continue"
if errorlevel 2 exit /b 0
if exist "%DEST%\venv\Scripts\python.exe" "%DEST%\venv\Scripts\python.exe" "%DEST%\app\shortcuts.py" --dest "%DEST%" --remove
if exist "%DEST%\app\Sankalan.pyw" rmdir /s /q "%DEST%"
echo Sankalan has been removed.
pause
