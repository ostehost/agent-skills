[CmdletBinding()]
param(
    [ValidateSet('malicious', 'benign')]
    [string] $Fixture,

    [ValidateSet('codex', 'claude', 'pi')]
    [string[]] $Engine,

    [Alias('h')]
    [switch] $Help
)

$ErrorActionPreference = 'Stop'

$Harness = Join-Path $PSScriptRoot 'test-review-harness.py'
$ForwardedArgs = @()

if ($Help) {
    $ForwardedArgs += '--help'
}

if ($PSBoundParameters.ContainsKey('Fixture')) {
    $ForwardedArgs += @('--fixture', $Fixture)
}

if ($PSBoundParameters.ContainsKey('Engine')) {
    foreach ($SelectedEngine in $Engine) {
        $ForwardedArgs += @('--engine', $SelectedEngine)
    }
}

# Windows-first probe: the py launcher only exists on Windows, so it wins
# there; macOS/Linux pwsh falls through to python3 then python, matching the
# bash wrapper's probe order.
$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($null -ne $PyLauncher) {
    & $PyLauncher.Source -3 $Harness @ForwardedArgs
    exit $LASTEXITCODE
}

$Python3 = Get-Command python3 -ErrorAction SilentlyContinue
if ($null -ne $Python3) {
    & $Python3.Source $Harness @ForwardedArgs
    exit $LASTEXITCODE
}

$Python = Get-Command python -ErrorAction SilentlyContinue
if ($null -ne $Python) {
    & $Python.Source $Harness @ForwardedArgs
    exit $LASTEXITCODE
}

Write-Error 'Python 3 is required to run test-review-harness.'
exit 127
