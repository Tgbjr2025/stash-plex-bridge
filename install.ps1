<#
.SYNOPSIS
  Bootstrap and run stash-plex-bridge on Windows.
.DESCRIPTION
  Ensures git + Python 3.11 are installed (via winget), creates a venv in
  .\bridge\.venv, installs Python deps, and launches bridge.installer.
  Safe to rerun.
.PARAMETER Args
  Forwarded to the Python installer (e.g. --force, --phase detect).
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Has-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Install-ViaWinget($id, $friendly) {
    Write-Host "[bridge] installing $friendly via winget..."
    winget install --id $id --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed to install $friendly (exit $LASTEXITCODE)"
    }
    # Refresh PATH for current session
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + `
                ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

# --- 1. Ensure git ---
if (-not (Has-Command git)) {
    Install-ViaWinget "Git.Git" "Git"
}

# --- 2. Ensure python ---
$python = $null
foreach ($cmd in @("python", "py")) {
    if (Has-Command $cmd) {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3\.(1[0-9]|[2-9][0-9])") {
            $python = $cmd
            break
        }
    }
}
if (-not $python) {
    Install-ViaWinget "Python.Python.3.11" "Python 3.11"
    $python = "python"
}

# --- 3. Create venv ---
$Venv = Join-Path $ProjectRoot "bridge\.venv"
if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
    Write-Host "[bridge] creating venv at $Venv"
    & $python -m venv $Venv
}
$VenvPy = Join-Path $Venv "Scripts\python.exe"

# --- 4. Install deps ---
$ReqHashFile = Join-Path $ProjectRoot "bridge\.reqs.sha256"
$ReqFile = Join-Path $ProjectRoot "requirements.txt"
$CurrentHash = (Get-FileHash $ReqFile -Algorithm SHA256).Hash
$PrevHash = if (Test-Path $ReqHashFile) { Get-Content $ReqHashFile } else { "" }

if ($CurrentHash -ne $PrevHash) {
    Write-Host "[bridge] installing Python deps"
    & $VenvPy -m pip install --upgrade pip | Out-Null
    & $VenvPy -m pip install -r $ReqFile
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    Set-Content -Path $ReqHashFile -Value $CurrentHash
} else {
    Write-Host "[bridge] deps up to date"
}

# --- 5. Lock down state.json ACL if it exists ---
$StateFile = Join-Path $ProjectRoot "state.json"
if (Test-Path $StateFile) {
    icacls $StateFile /inheritance:r /grant:r "$env:USERNAME:F" | Out-Null
}

# --- 6. Launch installer ---
Write-Host "[bridge] launching installer..."
& $VenvPy -m bridge.installer @Args
exit $LASTEXITCODE
