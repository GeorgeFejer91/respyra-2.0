param([switch]$GenerateIcons)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
if (-not [Environment]::Is64BitOperatingSystem) { throw 'The installer target is Windows x64.' }
$stagingRoot = Join-Path $repoRoot '.for-ai-local/packaging'
New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null
$env:UV_PROJECT_ENVIRONMENT = Join-Path $stagingRoot 'venv'
try {
    py -3.10 -m uv sync --frozen --no-dev --no-editable --python 3.10.11 --reinstall-package mpi
    if ($LASTEXITCODE -ne 0) { throw 'Locked runtime sync failed.' }
} finally { Remove-Item Env:UV_PROJECT_ENVIRONMENT }
$archive = Join-Path $stagingRoot 'python-3.10.11-embed-amd64.zip'
if (-not (Test-Path -LiteralPath $archive)) {
    Invoke-WebRequest 'https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip' -OutFile $archive
}
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne '608619f8619075629c9c69f361352a0da6ed7e62f83a0e19c63e0ea32eb7629d') {
    throw 'Embedded Python checksum mismatch; no installer was built.'
}
$buildPython = Join-Path $stagingRoot 'venv/Scripts/python.exe'
& $buildPython scripts/build_recorder.py
if ($LASTEXITCODE -ne 0) { throw 'Pinned native recorder build failed.' }
if ($GenerateIcons) {
    pnpm tauri icon assets/icon.svg
    if ($LASTEXITCODE -ne 0) { throw 'Icon conversion failed.' }
}
& $buildPython scripts/package_runtime.py
if ($LASTEXITCODE -ne 0) { throw 'Embedded runtime verification failed.' }
pnpm install --frozen-lockfile
if ($LASTEXITCODE -ne 0) { throw 'Locked frontend install failed.' }
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
pnpm tauri build --config src-tauri/installer.conf.json --bundles nsis -- --locked
if ($LASTEXITCODE -ne 0) { throw 'Windows installer build failed.' }
$output = Join-Path $repoRoot 'dist'
New-Item -ItemType Directory -Force -Path $output | Out-Null
$version = (Get-Content package.json -Raw | ConvertFrom-Json).version
$productName = (Get-Content src-tauri/tauri.conf.json -Raw | ConvertFrom-Json).productName
$name = "${productName}_${version}_x64-setup.exe"
Copy-Item -LiteralPath (Join-Path $repoRoot "src-tauri/target/release/bundle/nsis/$name") -Destination (Join-Path $output $name)
$checksum = (Get-FileHash -LiteralPath (Join-Path $output $name) -Algorithm SHA256).Hash.ToLowerInvariant()
"$checksum  $name" | Set-Content -LiteralPath (Join-Path $output 'SHA256SUMS.txt') -Encoding ascii
Copy-Item -LiteralPath (Join-Path $stagingRoot 'engine/manifest.json') -Destination (Join-Path $output 'runtime-manifest.json')
Write-Output "Installer ready: $output\$name"
