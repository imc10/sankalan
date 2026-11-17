; Sankalan installer (NSIS 3.08 or later). Per-user, no admin rights (NF-2, DEP-01): installs to
; %LOCALAPPDATA%\Programs\Sankalan with Start menu and desktop shortcuts named "Sankalan". No publisher or company
; name anywhere (UI-4, NF-6). An update is this installer run over the old one (SEC-6, DEP-10): the program files are
; replaced, the data folder is never touched. Uninstall asks whether to delete the data (T26, DEP-11, DEP-12).
;
;   makensis /DSRC=<dist\Sankalan> /DOUT=<setup.exe> /DVERSION=2.0.0 /DVERSION_NUM=2.0.0.0 [/DSIGN=<sign_one.bat>] installer.nsi
;
; With SIGN defined, makensis signs the uninstaller it embeds and the finished installer (SIGN "<file>" must exit 0).
Unicode true
!pragma warning disable 9100 ; no LegalCopyright key: it would name a company (NF-6)
ManifestDPIAware true
!include "MUI2.nsh"
!include "LogicLib.nsh"

!ifndef SRC
  !define SRC "..\dist\Sankalan"
!endif
!ifndef VERSION
  !error "Pass /DVERSION=<version> (packaging\version.py)"
!endif
!ifndef VERSION_NUM
  !error "Pass /DVERSION_NUM=<a.b.c.d> (packaging\version.py --numeric)"
!endif
!ifndef OUT
  !define OUT "..\dist\Sankalan-Setup-${VERSION}.exe"
!endif
!define APP "Sankalan"
!define EXE "Sankalan.exe"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP}"

!ifdef SIGN
  !uninstfinalize 'call "${SIGN}" "%1"' = 0
  !finalize 'call "${SIGN}" "%1"' = 0
!endif

Name "${APP}"
Caption "${APP} ${VERSION} setup"
UninstallCaption "Uninstall ${APP}"
BrandingText "${APP} ${VERSION}"
OutFile "${OUT}"
RequestExecutionLevel user
InstallDir "$LOCALAPPDATA\Programs\${APP}"
SetCompressor /SOLID lzma
ShowInstDetails nevershow
ShowUninstDetails nevershow

VIProductVersion "${VERSION_NUM}"
VIAddVersionKey "ProductName" "${APP}"
VIAddVersionKey "FileDescription" "${APP} setup"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "ProductVersion" "${VERSION}"

!define MUI_ICON "sankalan.ico"
!define MUI_UNICON "sankalan.ico"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\${EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Start ${APP}"
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

!define RUNNING_TEXT "${APP} is open. Close it, then click Retry."

; Sankalan (or one of its reader workers) is running when its exe can't be opened for writing.
!macro WAIT_UNTIL_CLOSED
  ${If} ${FileExists} "$INSTDIR\${EXE}"
    ${Do}
      ClearErrors
      FileOpen $0 "$INSTDIR\${EXE}" a
      ${IfNot} ${Errors}
        FileClose $0
        ${Break}
      ${EndIf}
      MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "${RUNNING_TEXT}" /SD IDCANCEL IDRETRY +2
      Abort
    ${Loop}
  ${EndIf}
!macroend

Function .onInit
  !insertmacro WAIT_UNTIL_CLOSED
FunctionEnd

Function un.onInit
  !insertmacro WAIT_UNTIL_CLOSED
FunctionEnd

Section "Install"
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  ; Update in place: the previous version's program files go first, so none of them are left behind.
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\${EXE}"
  File /r "${SRC}\*.*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Sankalan 1.x put its Start menu entry in a folder.
  Delete "$SMPROGRAMS\${APP}\${APP}.lnk"
  RMDir "$SMPROGRAMS\${APP}"
  CreateShortcut "$SMPROGRAMS\${APP}.lnk" "$INSTDIR\${EXE}" "" "$INSTDIR\${EXE}" 0
  CreateShortcut "$DESKTOP\${APP}.lnk" "$INSTDIR\${EXE}" "" "$INSTDIR\${EXE}" 0

  WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "${APP}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\${EXE},0"
  WriteRegStr HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  ; T26: ask about the data. No (the default, and the answer for a silent uninstall) keeps everything.
  MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "Do you also want to delete your Sankalan data?$\r$\n$\r$\nYes deletes the data folder with all clients, templates, runs and saved analyses, and Sankalan's settings and logs. This can't be undone.$\r$\n$\r$\nNo keeps your data, so a later install shows it again." /SD IDNO IDNO keep_data
    ExecWait '"$INSTDIR\${EXE}" --remove-data' $0
    ${If} $0 == 2
      MessageBox MB_OK|MB_ICONINFORMATION "Your data folder was not deleted because it doesn't look like a Sankalan data folder. Check it and delete it yourself if you no longer need it." /SD IDOK
    ${ElseIf} $0 != 0
      MessageBox MB_OK|MB_ICONINFORMATION "Some of Sankalan's data could not be deleted. Close any program using it, then delete it yourself." /SD IDOK
    ${EndIf}
  keep_data:

  Delete "$SMPROGRAMS\${APP}.lnk"
  Delete "$DESKTOP\${APP}.lnk"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "${UNINST_KEY}"
SectionEnd
