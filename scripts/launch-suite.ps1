$ErrorActionPreference = 'Stop'
$installation = Split-Path -Parent $PSScriptRoot
$programs = @(
    (Join-Path $installation 'suite/polar/polar-stream-mini.exe'),
    (Join-Path $installation 'suite/vernier/vernier-stream-mini.exe'),
    (Join-Path $installation 'respyra-desktop.exe')
)
foreach ($program in $programs) {
    if (-not (Test-Path -LiteralPath $program -PathType Leaf)) {
        throw "Suite program is missing: $program"
    }
}
foreach ($program in $programs) {
    Start-Process -FilePath $program -WorkingDirectory (Split-Path -Parent $program)
}
