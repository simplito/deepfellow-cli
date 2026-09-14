# DeepFellow CLI installer for native Windows.
#
# Windows itself is not a supported runtaget - the CLI (and install.sh) require a POSIX
# shell and Docker Compose semantics that only WSL provides. This script makes sure WSL is
# ready and then re-runs the real installer (install.sh) inside it.

param(
    [switch]$Dev
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host $msg
}

function Write-ErrorAndExit($msg) {
    Write-Host $msg -ForegroundColor Red
    exit 1
}

$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) {
    Write-ErrorAndExit @"
DeepFellow CLI requires WSL (Windows Subsystem for Linux) on Windows.

WSL was not found on this machine. Install it by running (as Administrator):

    wsl --install

Then restart your computer and re-run this script.
"@
}

$distros = @(wsl.exe -l -q 2>$null) | Where-Object { $_ -and $_.Trim() -ne "" }
if (-not $distros -or $distros.Count -eq 0) {
    Write-ErrorAndExit @"
WSL is installed but no Linux distribution is set up yet.

Install one by running (as Administrator):

    wsl --install -d Ubuntu

Then restart your computer, open the Ubuntu app once to finish setup, and re-run this script.
"@
}

Write-Step "Using WSL distribution to install deepfellow..."

$bashArgs = ""
if ($Dev) {
    $bashArgs = "--dev"
}

$bashCommand = "set -o pipefail; curl -sSL https://deepfellow.ai/install.sh | bash -s -- $bashArgs"
wsl.exe bash -lc $bashCommand
if ($LASTEXITCODE -ne 0) {
    Write-ErrorAndExit "Installation failed inside WSL. See output above for details."
}

Write-Host "Installed successfully! Run 'deepfellow --help' from inside your WSL distribution." -ForegroundColor Green
