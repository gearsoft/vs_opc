<#
PowerShell helper script for `vs_opc` development setup.
Usage (PowerShell):
  1. Install Python (see README). Make sure `python` is on PATH.
  2. Run this script from the `vs_opc` folder:
     .\setup_dev.ps1

What it does:
  - Creates a virtual environment in .venv
  - Activates it (instructions shown) or attempts to run activation in the current session
  - Upgrades pip and installs packages from requirements.txt
  - Runs pytest
#>

# Fail on errors
$ErrorActionPreference = 'Stop'

Write-Host "Running vs_opc development setup script..." -ForegroundColor Cyan

# Check python
try {
    $pyVer = & python --version 2>&1
} catch {
    Write-Host "python not found on PATH. Install Python and re-run this script." -ForegroundColor Red
    exit 1
}

Write-Host "Detected: $pyVer" -ForegroundColor Green

$venvDir = "$PSScriptRoot\\.venv"
if (-not (Test-Path $venvDir)) {
    Write-Host "Creating virtual environment in .venv..." -ForegroundColor Cyan
    & python -m venv $venvDir
} else {
    Write-Host ".venv already exists, skipping venv creation." -ForegroundColor Yellow
}

$activate = Join-Path $venvDir 'Scripts\Activate.ps1'
if (Test-Path $activate) {
    Write-Host "To activate the environment in this session run:" -ForegroundColor Green
    Write-Host "    .\\.venv\\Scripts\\Activate.ps1" -ForegroundColor White
    Write-Host "Attempting to activate in current session..." -ForegroundColor Cyan
    try {
        . $activate
    } catch {
        Write-Host "Activation failed in this session (ExecutionPolicy?). You can still activate with the command shown above." -ForegroundColor Yellow
    }
} else {
    Write-Host "Activation script not found at $activate" -ForegroundColor Red
}

Write-Host "Upgrading pip and installing requirements..." -ForegroundColor Cyan
& python -m pip install --upgrade pip
if (Test-Path "$PSScriptRoot\\requirements.txt") {
    & python -m pip install -r "$PSScriptRoot\\requirements.txt"
} else {
    Write-Host "No requirements.txt found, skipping install." -ForegroundColor Yellow
}

Write-Host "Running tests (pytest) if available..." -ForegroundColor Cyan
try {
    # Ensure the project root is discoverable by Python so imports like `from vs_opc.client import ...`
    # work during test collection. Set PYTHONPATH for this process to the script folder.
    $env:PYTHONPATH = $PSScriptRoot
    & python -m pytest
} catch {
    Write-Host "pytest failed or not installed. Install pytest manually if you need tests." -ForegroundColor Yellow
}

Write-Host "Setup complete." -ForegroundColor Green
