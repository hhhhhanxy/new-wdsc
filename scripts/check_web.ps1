$ErrorActionPreference = "Stop"

$Port = 5000
$HostName = "127.0.0.1"
$url = "http://$HostName`:$Port/healthz"
try {
    $response = Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "Web service is OK: http://$HostName`:$Port/"
        exit 0
    }
    Write-Host "Unexpected status: $($response.StatusCode)"
    exit 1
} catch {
    Write-Host "Web service is not reachable at http://$HostName`:$Port/"
    Write-Host $_.Exception.Message
    exit 1
}
