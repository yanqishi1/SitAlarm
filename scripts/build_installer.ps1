param(
  [switch]$BuildExe,
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

function Find-ISCC {
  $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }

  $candidates = @(
    'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
    'C:\Program Files\Inno Setup 6\ISCC.exe'
  )
  foreach ($c in $candidates) {
    if (Test-Path $c) { return $c }
  }
  return $null
}

$root = Get-ProjectRoot
Push-Location $root
try {
  $version = Get-AppVersion $root
  Write-Host "SitAlarm version: $version"

  if ($BuildExe) {
    & powershell.exe -ExecutionPolicy Bypass -File (Join-Path $root 'scripts\build_exe.ps1') -Clean -Mode onefile -IndexUrl $IndexUrl -TrustedHost $TrustedHost
  }

  $exe = Join-Path $root 'dist\SitAlarm.exe'
  if (-not (Test-Path $exe)) {
    throw "Missing $exe. Run scripts\\build_exe.ps1 first, or pass -BuildExe." 
  }

  $iscc = Find-ISCC
  if (-not $iscc) {
    throw "Inno Setup compiler (ISCC.exe) not found. Install Inno Setup 6, then re-run this script."
  }

  New-Item -ItemType Directory -Force (Join-Path $root 'release') | Out-Null

  Write-Host "Building installer with: $iscc"
  & $iscc (Join-Path $root 'installer\SitAlarm.iss') "/DAppVersion=$version"

  $setup = Join-Path $root "release\SitAlarm-Setup-$version.exe"
  if (Test-Path $setup) {
    Write-Host "OK: $setup"
  } else {
    Write-Host 'Installer build finished. Check release/ for output.'
  }
}
finally {
  Pop-Location
}
