param(
  [switch]$Clean,
  [ValidateSet('onefile','onedir')]
  [string]$Mode = 'onefile',
  [string]$VenvPath = '.venv-win',
  [string]$PyLauncher = 'py',
  [string]$PyVersion = '3.8',
  [string]$IndexUrl = 'http://mirrors.aliyun.com/pypi/simple',
  [string]$TrustedHost = 'mirrors.aliyun.com'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-ProjectRoot {
  $here = Split-Path -Parent $PSCommandPath
  return (Resolve-Path (Join-Path $here '..')).Path
}

function Get-AppVersion([string]$root) {
  $init = Join-Path $root 'sitalarm\__init__.py'
  $line = Select-String -Path $init -Pattern '^__version__\s*=\s*"(?<v>[^"]+)"' | Select-Object -First 1
  if (-not $line) { throw "Could not find __version__ in $init" }
  return $line.Matches[0].Groups['v'].Value
}

function Resolve-Python {
  param([string]$root)

  $launcher = Get-Command $PyLauncher -ErrorAction SilentlyContinue
  if ($launcher) {
    $args = @("-$PyVersion", '-c', 'import sys; print(sys.executable)')
    try {
      $exe = & $PyLauncher @args 2>$null
      if ($LASTEXITCODE -eq 0 -and $exe) {
        return $PyLauncher
      }
    } catch {
      # fall through
    }
  }

  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) { return 'python' }

  throw "Python not found. Install Python 3.8+ (python.org) or ensure 'py' launcher exists." 
}

$root = Get-ProjectRoot
Push-Location $root
try {
  $version = Get-AppVersion $root
  Write-Host "SitAlarm version: $version"

  if ($Clean) {
    if (Test-Path 'build') { Remove-Item -Recurse -Force 'build' }
    if (Test-Path 'dist') { Remove-Item -Recurse -Force 'dist' }
  }

  $pyCmd = Resolve-Python $root

  $venvFull = Join-Path $root $VenvPath
  $venvPy = Join-Path $venvFull 'Scripts\python.exe'

  if (-not (Test-Path $venvPy)) {
    Write-Host "Creating venv at $VenvPath using $pyCmd -$PyVersion ..."
    if ($pyCmd -eq $PyLauncher) {
      & $pyCmd "-$PyVersion" -m venv $VenvPath
    } else {
      & $pyCmd -m venv $VenvPath
    }
  }

  Write-Host 'Installing build dependencies (this can take a while)...'
  & $venvPy -m pip install -U pip -i $IndexUrl --trusted-host $TrustedHost
  & $venvPy -m pip install -r requirements-win-build.txt -i $IndexUrl --trusted-host $TrustedHost

  # Create a Windows .ico from logo.png for EXE/installer icons.
  $icoPath = Join-Path $root 'installer\icon.ico'
  & $venvPy -m pip install pillow -i $IndexUrl --trusted-host $TrustedHost
  & $venvPy (Join-Path $root 'scripts\make_ico.py') (Join-Path $root 'logo.png') $icoPath

  $modeArgs = @()
  if ($Mode -eq 'onefile') { $modeArgs += '--onefile' }

  Write-Host "Building EXE ($Mode)..."
  & $venvPy -m PyInstaller --noconfirm --clean --windowed @modeArgs `
    --name SitAlarm `
    --icon $icoPath `
    --add-data 'logo.png;.' `
    --add-data 'sitalarm/assets;sitalarm/assets' `
    --collect-all mediapipe `
    main.py

  $exe = Join-Path $root 'dist\SitAlarm.exe'
  if (-not (Test-Path $exe)) { throw "Build finished but EXE not found at $exe" }

  Write-Host "OK: $exe"
  Write-Host 'Tip: run dist\SitAlarm.exe to smoke-test.'
}
finally {
  Pop-Location
}
