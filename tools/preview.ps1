param(
    [switch]$Interactive,
    [ValidateSet('main', 'spool', 'colour', 'recovery', 'home')][string]$View = 'main',
    [ValidateSet('ready', 'printing', 'paused')][string]$State = 'ready',
    [ValidateRange(1, 8)][int]$Tools = 8,
    [int]$Selected = 0,
    [int]$Width = 800,
    [int]$Height = 480,
    [string]$Theme = 'z-bolt',
    [string]$KlipperScreen = "$PSScriptRoot/../../KlipperScreen",
    [switch]$NoSpoolman
)
$ErrorActionPreference = 'Stop'
$repoPath = (Resolve-Path "$PSScriptRoot/..").Path
$ksPath = (Resolve-Path $KlipperScreen).Path
$linuxRepo = (wsl -- wslpath -a $repoPath).Trim()
$linuxKS = (wsl -- wslpath -a $ksPath).Trim()
$outputName = if ($View -eq 'home') { "home-$Theme" } else { "$View-$State" }
$previewArgs = @('python3', "$linuxRepo/tools/preview.py", '--klipperscreen', $linuxKS,
    '--view', $View, '--state', $State, '--tools', "$Tools", '--selected', "$Selected",
    '--width', "$Width", '--height', "$Height", '--theme', $Theme,
    '--output', "$linuxRepo/preview/$outputName.png")
if ($NoSpoolman) { $previewArgs += '--no-spoolman' }
if ($Interactive) {
    $previewArgs += '--interactive'
    & wsl -- @previewArgs
} else {
    & wsl -- env GDK_BACKEND=x11 xvfb-run -a @previewArgs
}
exit $LASTEXITCODE
