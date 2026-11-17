@echo off
REM Signs one file (makensis calls this for the uninstaller and the installer: installer.nsi /DSIGN=...).
REM The certificate and timestamp server come from the SANKALAN_* variables (see sign_files.ps1).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sign_files.ps1" -Path "%~1"
exit /b %ERRORLEVEL%
