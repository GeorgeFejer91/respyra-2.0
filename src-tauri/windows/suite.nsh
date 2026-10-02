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
  SetOutPath "$INSTDIR\suite\vernier"
  CreateShortCut "$SMPROGRAMS\Respyra 2.0\Vernier Stream Mini.lnk" "$INSTDIR\suite\vernier\vernier-stream-mini.exe"
  SetOutPath "$INSTDIR"
  CreateShortCut "$SMPROGRAMS\Respyra 2.0\Launch full suite.lnk" "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "$INSTDIR\suite\launch-suite.ps1"' "$INSTDIR\respyra-desktop.exe"
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  Delete "$SMPROGRAMS\Respyra 2.0\Polar Stream Mini.lnk"
  Delete "$SMPROGRAMS\Respyra 2.0\Vernier Stream Mini.lnk"
  Delete "$SMPROGRAMS\Respyra 2.0\Launch full suite.lnk"
!macroend
