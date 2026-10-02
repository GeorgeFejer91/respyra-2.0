$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$testRoot = Join-Path $repoRoot '.for-ai-local/suite-launch-test'
$absoluteRoot = [IO.Path]::GetFullPath($repoRoot).TrimEnd('\') + '\'
if (-not [IO.Path]::GetFullPath($testRoot).StartsWith($absoluteRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Test directory is outside the workspace.'
}
if (Test-Path -LiteralPath $testRoot) { Remove-Item -LiteralPath $testRoot -Recurse -Force }
New-Item -ItemType Directory -Path (Join-Path $testRoot 'suite/polar'), (Join-Path $testRoot 'suite/vernier') -Force | Out-Null
$launcher = Join-Path $testRoot 'suite/launch-suite.ps1'
Copy-Item -LiteralPath (Join-Path $repoRoot 'scripts/launch-suite.ps1') -Destination $launcher
$expectedPrograms = @('suite/polar/polar-stream-mini.exe', 'suite/vernier/vernier-stream-mini.exe', 'respyra-desktop.exe')
foreach ($program in $expectedPrograms) { New-Item -ItemType File -Path (Join-Path $testRoot $program) | Out-Null }
$expected = ($expectedPrograms | ForEach-Object { Join-Path $testRoot $_ }) -join '|'
$global:SuiteStarts = @()
function Start-Process {
    param([string]$FilePath, [string]$WorkingDirectory)
    $global:SuiteStarts += $FilePath
}
. $launcher
if ($global:SuiteStarts.Count -ne 3 -or ($global:SuiteStarts -join '|') -ne $expected) {
    throw "The suite launcher paths differ: $($global:SuiteStarts -join '|') expected $expected"
}
Remove-Item -LiteralPath (Join-Path $testRoot $expectedPrograms[1])
$global:SuiteStarts = @()
$failed = $false
try { . $launcher } catch { $failed = $true }
if (-not $failed -or $global:SuiteStarts.Count -ne 0) { throw 'The launcher started a partial suite after a missing program.' }
Write-Output 'Suite launcher paths and all-or-none validation passed.'
