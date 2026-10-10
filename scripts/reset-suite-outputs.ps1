# The suite upgrade resets output selections; devices and recordings stay intact.
$ErrorActionPreference = 'Stop'
$preferenceRoot = [Environment]::GetFolderPath('ApplicationData')
foreach ($app in @('dev.georgefejer.polarstreammini', 'dev.georgefejer.vernierstreammini')) {
    $path = Join-Path $preferenceRoot "$app/preferences.json"
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
    $original = [IO.File]::ReadAllText($path)
    $backup = "$path.before-respyra-0.3.12"
    if (-not (Test-Path -LiteralPath $backup)) { [IO.File]::Copy($path, $backup) }
    try { $saved = $original | ConvertFrom-Json }
    catch { $saved = [PSCustomObject]@{} }
    if ($null -eq $saved -or $saved -isnot [PSCustomObject]) { $saved = [PSCustomObject]@{} }
    # Removing these fields asks the pinned Mini runtime for its canonical defaults.
    foreach ($field in @('outputMode', 'polarOutputs', 'vernierOutputs')) {
        $saved.PSObject.Properties.Remove($field)
    }
    $temporary = "$path.respyra-reset.tmp"
    try {
        [IO.File]::WriteAllText($temporary, ($saved | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))
        [IO.File]::Replace($temporary, $path, [NullString]::Value)
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
    }
}
