# Launches the Streamlit dashboard and a public Cloudflare tunnel.
# Usage:  powershell -ExecutionPolicy Bypass -File serve.ps1
# The public URL is printed below and also written to tunnel.log.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Locate the real Python (Store aliases on PATH are stubs).
$py = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python" -Filter python.exe -Recurse -ErrorAction SilentlyContinue |
      Where-Object { $_.FullName -notlike '*Scripts*' } | Select-Object -First 1 -ExpandProperty FullName
if (-not $py) { throw "Python not found. Install with: winget install Python.Python.3.12" }

# Locate cloudflared.
$cf = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter cloudflared.exe -Recurse -ErrorAction SilentlyContinue |
      Select-Object -First 1 -ExpandProperty FullName
if (-not $cf) { $cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source }

Write-Host "Starting Streamlit on http://localhost:8501 ..."
Start-Process -FilePath $py -ArgumentList "-m","streamlit","run","app.py" -WorkingDirectory $PSScriptRoot

if ($cf) {
    Write-Host "Starting public tunnel (URL will appear shortly)..."
    & $cf tunnel --url http://localhost:8501 --no-autoupdate
} else {
    Write-Host "cloudflared not found; install with: winget install Cloudflare.cloudflared"
    Write-Host "Dashboard is available locally at http://localhost:8501"
}
