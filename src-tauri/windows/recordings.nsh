!macro NSIS_HOOK_PREINSTALL
  ClearErrors
  CreateDirectory "$INSTDIR\data"
  IfErrors 0 +2
    Abort "Cannot create the Respyra recordings folder at $INSTDIR\data"
!macroend
