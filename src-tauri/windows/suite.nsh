!macro NSIS_HOOK_PREINSTALL
  ClearErrors
  CreateDirectory "$INSTDIR\data"
  IfErrors 0 +2
    Abort "Cannot create the Respyra recordings folder at $INSTDIR\data"
!macroend

!macro NSIS_HOOK_POSTINSTALL
  CreateDirectory "$SMPROGRAMS\Respyra 2.0"
  SetOutPath "$INSTDIR\suite\polar"
  CreateShortCut "$SMPROGRAMS\Respyra 2.0\Polar Stream Mini.lnk" "$INSTDIR\suite\polar\polar-stream-mini.exe"
  CreateShortCut "$DESKTOP\Polar Stream Mini.lnk" "$INSTDIR\suite\polar\polar-stream-mini.exe"
  SetOutPath "$INSTDIR\suite\vernier"
  CreateShortCut "$SMPROGRAMS\Respyra 2.0\Vernier Stream Mini.lnk" "$INSTDIR\suite\vernier\vernier-stream-mini.exe"
  CreateShortCut "$DESKTOP\Vernier Stream Mini.lnk" "$INSTDIR\suite\vernier\vernier-stream-mini.exe"
  SetOutPath "$INSTDIR"
  CreateShortCut "$DESKTOP\Respyra 2.0.lnk" "$INSTDIR\respyra-desktop.exe"
  Delete "$SMPROGRAMS\Respyra 2.0\Launch full suite.lnk"
  CreateShortCut "$SMPROGRAMS\Respyra 2.0\Launch Respyra Suite.lnk" "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "$INSTDIR\suite\launch-suite.ps1"' "$INSTDIR\suite\suite.ico"
  CreateShortCut "$DESKTOP\Launch Respyra Suite.lnk" "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "$INSTDIR\suite\launch-suite.ps1"' "$INSTDIR\suite\suite.ico"
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  Delete "$SMPROGRAMS\Respyra 2.0\Polar Stream Mini.lnk"
  Delete "$SMPROGRAMS\Respyra 2.0\Vernier Stream Mini.lnk"
  Delete "$SMPROGRAMS\Respyra 2.0\Launch full suite.lnk"
  Delete "$SMPROGRAMS\Respyra 2.0\Launch Respyra Suite.lnk"
  Delete "$DESKTOP\Respyra 2.0.lnk"
  Delete "$DESKTOP\Polar Stream Mini.lnk"
  Delete "$DESKTOP\Vernier Stream Mini.lnk"
  Delete "$DESKTOP\Launch Respyra Suite.lnk"
!macroend
