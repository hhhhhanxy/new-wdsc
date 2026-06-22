param(
    [string]$OutputDir = "dist\new-wdsc-offline",
    [switch]$IncludeData,
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

$pythonVersion = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($pythonVersion -ne "3.12") {
    throw "离线包需要使用 Python 3.12 制作，当前 $PythonExe 版本为 $pythonVersion。请安装 Python 3.12 后使用 -PythonExe 指定。"
}

$OutputPath = Join-Path $ProjectRoot $OutputDir
if (Test-Path $OutputPath) {
    Remove-Item -LiteralPath $OutputPath -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null

$excludeDirs = @(
    ".git", ".venv", ".uv-cache", ".pytest_cache", "__pycache__",
    "dist", ".agents", ".codex", ".claude", ".superpowers",
    ".codex-spreadsheet", "report_render_check", "tech_plan_render_check"
)
$excludeFiles = @(
    ".env", ".env.prod",
    "model_service.json",
    "web_server.log", "web_server.err.log", "web_server.out.log"
)

Get-ChildItem -Force $ProjectRoot | ForEach-Object {
    if ($excludeDirs -contains $_.Name) { return }
    if ($excludeFiles -contains $_.Name) { return }
    if (-not $IncludeData -and $_.Name -in @("uploads", "web")) {
        if ($_.Name -eq "web") {
            New-Item -ItemType Directory -Force -Path (Join-Path $OutputPath "web") | Out-Null
            Get-ChildItem -Force $_.FullName | Where-Object { $_.Name -ne "database.db" } | ForEach-Object {
                Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $OutputPath "web") -Recurse -Force
            }
        }
        return
    }
    Copy-Item -LiteralPath $_.FullName -Destination $OutputPath -Recurse -Force
}

Get-ChildItem -Force -Recurse -Directory $OutputPath |
    Where-Object { $excludeDirs -contains $_.Name } |
    Remove-Item -Recurse -Force

Get-ChildItem -Force -Recurse -File $OutputPath |
    Where-Object { ($excludeFiles -contains $_.Name) -or ($_.Extension -in @(".pyc", ".pyo")) } |
    Remove-Item -Force

New-Item -ItemType Directory -Force -Path (Join-Path $OutputPath "uploads") | Out-Null

Write-Host "Downloading wheels into packages/..."
New-Item -ItemType Directory -Force -Path (Join-Path $OutputPath "packages") | Out-Null
& $PythonExe -m pip download -r requirements.txt -d (Join-Path $OutputPath "packages")

$zipPath = "$OutputPath.zip"
if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $OutputPath "*") -DestinationPath $zipPath -Force
Write-Host "Offline package created:"
Write-Host $zipPath
