$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
$Port = 5000
$HostName = "127.0.0.1"

$existing = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq "Listen" } |
    Select-Object -First 1

if ($existing) {
    Write-Host "Port $Port is already in use by process $($existing.OwningProcess)."
    Write-Host "Open: http://$HostName`:$Port/"
    exit 0
}

$env:PORT = [string]$Port
$env:HOST = $HostName
$env:DEBUG = "false"
$env:USE_RELOADER = "false"
$env:UV_CACHE_DIR = Join-Path $ProjectRoot ".uv-cache"

Write-Host "Starting web service..."
Write-Host "Open: http://$HostName`:$Port/"
uv run python run.py
