param([switch]$Push)
$ErrorActionPreference = 'Stop'
$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$publishRoot = Join-Path (Split-Path $sourceRoot -Parent) 'respyra-2.0-pages'

function RunGit([string]$directory, [string[]]$gitArguments) {
    $output = & git -C $directory @gitArguments
    if ($LASTEXITCODE -ne 0) { throw "Git failed: $($gitArguments[0])" }
    return $output
}

if (@(RunGit $sourceRoot @('status', '--porcelain')).Count) {
    throw 'Commit the validated source before publishing the phone page.'
}
$sourceCommit = RunGit $sourceRoot @('rev-parse', 'HEAD')
Push-Location $sourceRoot
try {
    & pnpm prepare:web
    if ($LASTEXITCODE -ne 0) { throw 'Phone asset preparation failed.' }
} finally { Pop-Location }

if (!(Test-Path -LiteralPath $publishRoot)) {
    RunGit $sourceRoot @('fetch', 'origin')
    & git -C $sourceRoot show-ref --verify --quiet refs/heads/gh-pages
    if ($LASTEXITCODE -eq 0) {
        RunGit $sourceRoot @('worktree', 'add', $publishRoot, 'gh-pages')
    } else {
        & git -C $sourceRoot show-ref --verify --quiet refs/remotes/origin/gh-pages
        if ($LASTEXITCODE -eq 0) {
            RunGit $sourceRoot @('worktree', 'add', '-b', 'gh-pages', $publishRoot, 'origin/gh-pages')
        } else {
            # Start with an empty tree: no private backend/history in the site.
            $emptyPath = Join-Path $sourceRoot '.for-ai-local/pages-empty'
            New-Item -ItemType Directory -Path (Split-Path $emptyPath -Parent) -Force | Out-Null
            [IO.File]::WriteAllBytes($emptyPath, [byte[]]@())
            $tree = RunGit $sourceRoot @('hash-object', '-t', 'tree', '-w', $emptyPath)
            $initial = RunGit $sourceRoot @('commit-tree', $tree, '-m', 'Initialize static Respyra phone site')
            RunGit $sourceRoot @('update-ref', 'refs/heads/gh-pages', $initial, ('0' * 40))
            RunGit $sourceRoot @('worktree', 'add', $publishRoot, 'gh-pages')
        }
    }
}
if ((RunGit $publishRoot @('branch', '--show-current')) -ne 'gh-pages' -or
    [IO.Path]::GetFullPath((RunGit $publishRoot @('rev-parse', '--show-toplevel'))) -ne [IO.Path]::GetFullPath($publishRoot)) {
    throw 'The publication directory must be its own gh-pages worktree.'
}
if (@(RunGit $publishRoot @('status', '--porcelain')).Count) {
    throw 'The publication worktree has changes; review them before publishing.'
}
$files = @('index.html', 'remote.html', 'site.css', 'site.js', 'logo.svg', 'app.js', 'style.css', 'text-fit.js', 'remote-profile.js',
           'controller-ui.js', 'participant-options.js', 'action-queue.js', 'lsl-monitor.js', 'panel.json', 'vendor')
foreach ($name in $files) {
    Copy-Item -LiteralPath (Join-Path $sourceRoot "companion/$name") -Destination $publishRoot -Recurse -Force
}
$provenance = [ordered]@{ repository='https://github.com/GeorgeFejer91/respyra-2.0'; commit=$sourceCommit; profile='respyra.controller/1' }
$provenance | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $publishRoot 'source.json') -Encoding utf8
[IO.File]::WriteAllText((Join-Path $publishRoot '.nojekyll'), '')
RunGit $publishRoot (@('add', '--') + $files + @('source.json', '.nojekyll'))
& git -C $publishRoot diff --cached --quiet
if ($LASTEXITCODE -eq 1) {
    RunGit $publishRoot @('commit', '-m', "Publish Respyra site from $($sourceCommit.Substring(0,7))")
} elseif ($LASTEXITCODE -ne 0) { throw 'Cannot inspect the publication diff.' }
if ($Push) { RunGit $publishRoot @('push', 'origin', 'HEAD:gh-pages') }
Write-Output "Static site source: $sourceCommit"
Write-Output "Pages commit: $(RunGit $publishRoot @('rev-parse', 'HEAD'))"
