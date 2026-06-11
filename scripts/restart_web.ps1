$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ProjectRootPattern = $ProjectRoot.Replace("\", "\\")
$Port = 5000
$HostName = "127.0.0.1"

Write-Host "Stopping existing web service for project: $ProjectRoot"

$projectProcesses = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq "python.exe" -and
        $_.CommandLine -like "*run.py*" -and
        ($_.CommandLine -like "*$ProjectRoot*" -or $_.CommandLine -like "*$ProjectRootPattern*")
    }

foreach ($process in $projectProcesses) {
    Write-Host "Stopping process $($process.ProcessId): $($process.CommandLine)"
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 2

$env:PORT = [string]$Port
$env:HOST = $HostName
$env:DEBUG = "false"
$env:USE_RELOADER = "false"
$env:UV_CACHE_DIR = Join-Path $ProjectRoot ".uv-cache"

Set-Location $ProjectRoot
Write-Host "Starting web service at http://$HostName`:$Port/"
Start-Process -FilePath uv -ArgumentList @("run", "python", "run.py") -WorkingDirectory $ProjectRoot -WindowStyle Hidden

$url = "http://$HostName`:$Port/healthz"
for ($attempt = 1; $attempt -le 15; $attempt++) {
    Start-Sleep -Seconds 1
    try {
        $response = Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            Write-Host "Web service is OK: http://$HostName`:$Port/"
            exit 0
        }
    } catch {
        if ($attempt -eq 15) {
            Write-Host "Web service failed to start at http://$HostName`:$Port/"
            Write-Host $_.Exception.Message
            exit 1
        }
    }
}

Write-Host "Web service failed to start at http://$HostName`:$Port/"
exit 1
