param(
    [string]$HostName = "",
    [int]$Port = 0,
    [switch]$Production,
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

$venvPython = ".venv\Scripts\python.exe"
$venvReady = $false
if (Test-Path $venvPython) {
    try {
        $venvVersion = & $venvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        $venvReady = ($LASTEXITCODE -eq 0 -and $venvVersion -eq "3.12")
    } catch {
        $venvReady = $false
    }
}

if (-not $venvReady) {
    $pythonVersion = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($pythonVersion -ne "3.12") {
        throw "项目需要 Python 3.12，当前 $PythonExe 版本为 $pythonVersion。请安装 Python 3.12 后使用 -PythonExe 指定。"
    }
    Write-Host "Creating virtual environment with $PythonExe..."
    & $PythonExe -m venv .venv
}

if (Test-Path "packages") {
    Write-Host "Installing dependencies from local packages/..."
    & $venvPython -m pip install --no-index --find-links packages -r requirements.txt
} else {
    Write-Host "Installing dependencies from configured Python index..."
    & $venvPython -m pip install -r requirements.txt
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Warning "已创建 .env，请先配置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 后重新启动。"
    exit 1
}

if ($HostName) { $env:WEB_HOST = $HostName }
if ($Port -gt 0) { $env:WEB_PORT = "$Port" }

if ($Production) {
    & $venvPython scripts\run_waitress.py
} else {
    & $venvPython run.py
}
