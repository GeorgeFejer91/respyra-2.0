$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"

function Require-Success([string]$Action) {
    if ($LASTEXITCODE -ne 0) { throw "$Action failed (exit $LASTEXITCODE)." }
}

function Sha256([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $hash = [Security.Cryptography.SHA256]::Create()
    try { [BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $hash.Dispose(); $stream.Dispose() }
}

$miniRoot = Join-Path $repoRoot 'mini-streams'
if (-not (Test-Path -LiteralPath (Join-Path $miniRoot 'Cargo.toml'))) {
    throw 'Initialize the mini-streams submodule before packaging.'
}
$miniRevision = (& git -C $miniRoot rev-parse HEAD).Trim()
Require-Success 'Read Mini revision'
$pinnedRevision = (& git rev-parse ':mini-streams').Trim()
Require-Success 'Read pinned Mini revision'
if ($miniRevision -ne $pinnedRevision) { throw 'Mini checkout differs from the pinned submodule revision.' }
if (& git -C $miniRoot status --porcelain) { throw 'Mini checkout has uncommitted changes.' }
Require-Success 'Check Mini status'

$miniVersion = (Get-Content (Join-Path $miniRoot 'package.json') -Raw | ConvertFrom-Json).version
$respyraVersion = (Get-Content 'package.json' -Raw | ConvertFrom-Json).version
$miniTarget = if ($env:RESPYRA_MINI_TARGET_DIR) { [IO.Path]::GetFullPath($env:RESPYRA_MINI_TARGET_DIR) } else { Join-Path $miniRoot 'target' }
$sevenZip = @(
    (Get-Command 7z.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
    'C:\Program Files\7-Zip\7z.exe',
    'C:\Program Files (x86)\7-Zip\7z.exe'
) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
if (-not $sevenZip) { throw '7-Zip is required to inspect the finalized Mini installers.' }

$stage = Join-Path $repoRoot '.for-ai-local/suite'
$absoluteRoot = [IO.Path]::GetFullPath($repoRoot).TrimEnd('\') + '\'
$absoluteStage = [IO.Path]::GetFullPath($stage)
if (-not $absoluteStage.StartsWith($absoluteRoot, [StringComparison]::OrdinalIgnoreCase) -or
    -not $absoluteStage.Contains('\.for-ai-local\suite')) {
    throw 'Refusing to replace a suite staging directory outside this workspace.'
}
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'launch-suite.ps1') -Destination (Join-Path $stage 'launch-suite.ps1')
Copy-Item -LiteralPath (Join-Path $miniRoot 'LICENSE') -Destination (Join-Path $stage 'MINI-STREAMS-LICENSE')
$dist = Join-Path $repoRoot 'dist'
New-Item -ItemType Directory -Path $dist -Force | Out-Null

Push-Location -LiteralPath $miniRoot
try {
    npm ci
    Require-Success 'Locked Mini frontend install'
} finally { Pop-Location }

$miniArtifacts = @()
foreach ($app in @(
    @{ Kind = 'polar'; Product = 'Polar Stream Mini'; Exe = 'polar-stream-mini.exe' },
    @{ Kind = 'vernier'; Product = 'Vernier Stream Mini'; Exe = 'vernier-stream-mini.exe' }
)) {
    $appRoot = Join-Path $miniRoot "apps/$($app.Kind)-stream-mini"
    $configuredVersion = (Get-Content (Join-Path $appRoot 'tauri.conf.json') -Raw | ConvertFrom-Json).version
    if ($configuredVersion -ne $miniVersion) { throw "$($app.Product) version differs from package.json." }
    Push-Location -LiteralPath $appRoot
    $previousTarget = $env:CARGO_TARGET_DIR
    try {
        if ($env:RESPYRA_MINI_TARGET_DIR) { $env:CARGO_TARGET_DIR = $miniTarget }
        npm exec -- tauri build --bundles nsis --ci -- --locked
        Require-Success "$($app.Product) installer build"
    } finally {
        if ($previousTarget) { $env:CARGO_TARGET_DIR = $previousTarget }
        else { Remove-Item Env:CARGO_TARGET_DIR -ErrorAction SilentlyContinue }
        Pop-Location
    }
    $name = "$($app.Product)_${miniVersion}_x64-setup.exe"
    $installer = @(
        (Join-Path $miniTarget "x86_64-pc-windows-msvc/release/bundle/nsis/$name"),
        (Join-Path $miniTarget "release/bundle/nsis/$name")
    ) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if (-not $installer) { throw "Finalized Mini installer is missing: $name" }
    $destination = Join-Path $stage $app.Kind
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    $resources = @(Get-ChildItem -LiteralPath (Join-Path $appRoot 'resources') -File | Select-Object -ExpandProperty Name)
    & $sevenZip e $installer "-o$destination" $app.Exe $resources -y | Out-Null
    Require-Success "Extract $($app.Product) installer payload"
    if (-not (Test-Path -LiteralPath (Join-Path $destination $app.Exe) -PathType Leaf)) {
        throw "$($app.Product) executable was absent from its finalized installer."
    }
    $resourceHashes = [ordered]@{}
    foreach ($resource in $resources) {
        $extracted = Join-Path $destination $resource
        if (-not (Test-Path -LiteralPath $extracted -PathType Leaf) -or
            (Sha256 $extracted) -ne (Sha256 (Join-Path $appRoot "resources/$resource"))) {
            throw "$($app.Product) installed resource differs from the pinned source: $resource"
        }
        $resourceHashes[$resource] = Sha256 $extracted
    }
    $standaloneName = ($app.Product -replace ' ', '-') + "_${miniVersion}_x64-setup.exe"
    Copy-Item -LiteralPath $installer -Destination (Join-Path $dist $standaloneName)
    $miniArtifacts += [ordered]@{
        product = $app.Product
        installer = $standaloneName
        installer_sha256 = Sha256 (Join-Path $dist $standaloneName)
        executable = "suite/$($app.Kind)/$($app.Exe)"
        executable_sha256 = Sha256 (Join-Path $destination $app.Exe)
        resources = $resourceHashes
    }
}

pnpm package:windows
Require-Success 'Standalone Respyra installer build'
pnpm tauri build --config src-tauri/installer.conf.json --config src-tauri/suite.conf.json --bundles nsis -- --locked
Require-Success 'Suite installer build'
$tauriInstaller = Join-Path $repoRoot "src-tauri/target/release/bundle/nsis/Respyra 2.0_${respyraVersion}_x64-setup.exe"
if (-not (Test-Path -LiteralPath $tauriInstaller -PathType Leaf)) { throw 'Finalized suite installer is missing.' }
$suiteName = "Respyra-Suite_${respyraVersion}_x64-setup.exe"
Copy-Item -LiteralPath $tauriInstaller -Destination (Join-Path $dist $suiteName)
$standaloneName = "Respyra 2.0_${respyraVersion}_x64-setup.exe"
$manifest = [ordered]@{
    suite_version = $respyraVersion
    respyra_revision = (& git rev-parse HEAD).Trim()
    mini_revision = $miniRevision
    respyra_installer = $standaloneName
    respyra_installer_sha256 = Sha256 (Join-Path $dist $standaloneName)
    suite_installer = $suiteName
    suite_installer_sha256 = Sha256 (Join-Path $dist $suiteName)
    mini_apps = $miniArtifacts
}
$manifestPath = Join-Path $dist 'suite-manifest.json'
[IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 8) + [Environment]::NewLine,
    [Text.UTF8Encoding]::new($false))
$checksums = @($standaloneName, $suiteName, 'suite-manifest.json', 'runtime-manifest.json') + @($miniArtifacts | ForEach-Object { $_.installer })
$checksums | ForEach-Object { "$(Sha256 (Join-Path $dist $_))  $_" } |
    Set-Content -LiteralPath (Join-Path $dist 'SHA256SUMS.txt') -Encoding ascii
Write-Output "Suite installer ready: $dist\$suiteName"
