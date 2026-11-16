@echo off
REM Build, test, package and sign Sankalan on a Windows 10/11 PC.
REM Needs (installed once): Python 3.13 (64-bit) and NSIS (makensis on PATH).
REM Signing: set SANKALAN_PFX=path\to\certificate.pfx and SANKALAN_PFX_PASSWORD=...
REM   (needs signtool.exe from the Windows SDK on PATH).
REM On PCs with Smart App Control turned on, Windows blocks unsigned programs, so the packaged
REM app can only be self-tested (step 5) and used there once it is signed.
setlocal
cd /d "%~dp0\.."

echo === 1/7 Create build environment
py -3.13 -m venv .venv-build || goto :error
call .venv-build\Scripts\activate.bat
python -m pip install --upgrade pip >nul
python -m pip install -r requirements-lock.txt -r requirements-dev.txt || goto :error

echo === 2/7 Run the automated end-to-end tests
set QT_QPA_PLATFORM=offscreen
python -m pytest tests -q -p no:cacheprovider || goto :error
set QT_QPA_PLATFORM=

echo === 3/7 Build Sankalan.exe
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging\sankalan.spec || goto :error

echo === 4/7 Sign every program file in the app
if defined SANKALAN_PFX (
  powershell -NoProfile -ExecutionPolicy Bypass -File packaging\sign_files.ps1 -Folder dist\Sankalan -Pfx "%SANKALAN_PFX%" -Password "%SANKALAN_PFX_PASSWORD%" || goto :error
) else (
  echo SANKALAN_PFX not set - skipping signing.
  echo Windows will show "unknown publisher", and Smart App Control will block the app.
)

echo === 5/7 Self-test the packaged exe
if exist dist\selftest.json del dist\selftest.json
start "" /wait dist\Sankalan\Sankalan.exe --self-test --report dist\selftest.json
if not exist dist\selftest.json (
  echo Windows did not let Sankalan.exe run. On a PC with Smart App Control turned on this happens
  echo when the app is not signed: set SANKALAN_PFX and build again.
  goto :error
)
findstr /c:"\"result\": \"PASS\"" dist\selftest.json >nul || (
  echo Self-test FAILED - see dist\selftest.json
  goto :error
)
echo Self-test passed.

echo === 6/7 Build the installer
makensis /DSRC=..\dist\Sankalan /DOUT=..\dist\Sankalan-Setup-1.0.0.exe packaging\installer.nsi || goto :error

echo === 7/7 Sign the installer
if defined SANKALAN_PFX (
  signtool sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /f "%SANKALAN_PFX%" /p "%SANKALAN_PFX_PASSWORD%" dist\Sankalan-Setup-1.0.0.exe || goto :error
) else (
  echo SANKALAN_PFX not set - installer not signed.
)
echo.
echo Done: dist\Sankalan-Setup-1.0.0.exe
exit /b 0

:error
echo Build failed.
exit /b 1
