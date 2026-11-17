@echo off
REM Build, test, package and sign Sankalan on the Windows build PC (Tech spec: Packaging and security).
REM   1 tests  2 PyInstaller folder build  3 sign every program file  4 self-test the built app
REM   5 NSIS installer (makensis signs the uninstaller and the installer)  6 check the installer's signature
REM
REM Needs (installed once): Python 3.13 64-bit, NSIS 3.08+ (makensis on PATH or in Program Files),
REM and for signing the Windows SDK signtool plus the RSA OV certificate (USB token).
REM Signing: set SANKALAN_SIGN_THUMBPRINT=<certificate thumbprint>   (or SANKALAN_PFX + SANKALAN_PFX_PASSWORD
REM   for a test .pfx); optional SANKALAN_TIMESTAMP_URL=<the CA's timestamp server>. Signing needs internet for
REM   the timestamp; the app itself never uses the network.
REM Without a certificate the build still runs, unsigned: fine on a PC with Smart App Control off, blocked on
REM laptops with it on.
setlocal
cd /d "%~dp0\.."

set SIGNING=
if defined SANKALAN_SIGN_THUMBPRINT set SIGNING=1
if defined SANKALAN_PFX set SIGNING=1

echo === 0/6 Build environment
py -3.13 -m venv .venv-build || goto :error
call .venv-build\Scripts\activate.bat
python -m pip install --upgrade pip >nul
python -m pip install -r requirements-lock.txt -r requirements-dev.txt || goto :error
for /f %%v in ('python packaging\version.py') do set VERSION=%%v
for /f %%v in ('python packaging\version.py --numeric') do set VERSION_NUM=%%v
if not defined VERSION goto :error
echo Version %VERSION%

set MAKENSIS=makensis
where makensis >nul 2>&1 || set "MAKENSIS=%ProgramFiles(x86)%\NSIS\makensis.exe"

echo === 1/6 Automated tests
set QT_QPA_PLATFORM=offscreen
python -m pytest tests -q -p no:cacheprovider || goto :error
set QT_QPA_PLATFORM=

echo === 2/6 Build Sankalan.exe (folder build)
if exist dist\Sankalan rmdir /s /q dist\Sankalan
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging\sankalan.spec || goto :error

echo === 3/6 Sign every program file in the app
if defined SIGNING (
  powershell -NoProfile -ExecutionPolicy Bypass -File packaging\sign_files.ps1 -Path dist\Sankalan || goto :error
) else (
  echo No certificate set - the app is NOT signed. Smart App Control will block it on customer laptops.
)

echo === 4/6 Self-test of the built app
set EXPECT=
if defined SIGNING set EXPECT=--expect-signed
if exist dist\selftest.json del dist\selftest.json
start "" /wait dist\Sankalan\Sankalan.exe --self-test --report dist\selftest.json %EXPECT%
if not exist dist\selftest.json (
  echo Windows did not let Sankalan.exe run. With Smart App Control on this happens when the app is not signed.
  goto :error
)
findstr /c:"\"result\": \"PASS\"" dist\selftest.json >nul || (
  echo Self-test FAILED - see dist\selftest.json
  goto :error
)
echo Self-test passed.

echo === 5/6 Build the installer
set OUT=%CD%\dist\Sankalan-Setup-%VERSION%.exe
if exist "%OUT%" del "%OUT%"
if defined SIGNING (
  "%MAKENSIS%" "/DSRC=%CD%\dist\Sankalan" "/DOUT=%OUT%" /DVERSION=%VERSION% /DVERSION_NUM=%VERSION_NUM% "/DSIGN=%CD%\packaging\sign_one.bat" packaging\installer.nsi || goto :error
) else (
  "%MAKENSIS%" "/DSRC=%CD%\dist\Sankalan" "/DOUT=%OUT%" /DVERSION=%VERSION% /DVERSION_NUM=%VERSION_NUM% packaging\installer.nsi || goto :error
)

echo === 6/6 Check the installer's signature
if defined SIGNING (
  powershell -NoProfile -ExecutionPolicy Bypass -File packaging\sign_files.ps1 -Path "%OUT%" -VerifyOnly || goto :error
) else (
  echo Installer not signed.
)
echo.
echo Done: %OUT%
exit /b 0

:error
echo Build failed.
exit /b 1
