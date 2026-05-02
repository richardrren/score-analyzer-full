param(
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ScriptDir

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install pyinstaller

$mode = @()
if ($OneFile) {
    $mode += "--onefile"
}

$nodePath = Join-Path $ProjectRoot "node"

.\.venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --windowed `
    --name "ScoreReportTool" `
    --add-data "$nodePath;node" `
    --hidden-import "requests" `
    --hidden-import "urllib3" `
    --hidden-import "charset_normalizer" `
    --hidden-import "idna" `
    --hidden-import "certifi" `
    --hidden-import "numpy" `
    --hidden-import "pandas" `
    --hidden-import "openpyxl" `
    --hidden-import "reportlab" `
    --hidden-import "PySide6" `
    --collect-all "requests" `
    --collect-all "urllib3" `
    --collect-all "PySide6" `
    --collect-all "numpy" `
    @mode `
    main.py

Write-Host "`n打包完成！EXE文件位于: $ScriptDir\dist\ScoreReportTool.exe" -ForegroundColor Green
