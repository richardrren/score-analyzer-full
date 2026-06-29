param(
    [switch]$OneFile,
    [switch]$Optimize
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

if ($Optimize) {
    $mode += "--optimize=2"
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
    --hidden-import "openpyxl.styles" `
    --hidden-import "openpyxl.utils" `
    --hidden-import "openpyxl.writer.excel" `
    --hidden-import "reportlab" `
    --hidden-import "reportlab.pdfgen" `
    --hidden-import "reportlab.lib" `
    --hidden-import "reportlab.graphics" `
    --hidden-import "reportlab.platypus" `
    --hidden-import "PySide6" `
    --hidden-import "PySide6.QtWidgets" `
    --hidden-import "PySide6.QtCore" `
    --hidden-import "PySide6.QtGui" `
    --hidden-import "PySide6.QtPrintSupport" `
    --exclude-module "matplotlib" `
    --exclude-module "scipy" `
    --exclude-module "jupyter" `
    --exclude-module "notebook" `
    --exclude-module "numpy.testing" `
    --exclude-module "numpy.distutils" `
    --exclude-module "pandas.testing" `
    --exclude-module "pandas.tests" `
    --exclude-module "PySide6.Qt3DCore" `
    --exclude-module "PySide6.Qt3DExtras" `
    --exclude-module "PySide6.Qt3DInput" `
    --exclude-module "PySide6.Qt3DLogic" `
    --exclude-module "PySide6.Qt3DRender" `
    --exclude-module "PySide6.QtBluetooth" `
    --exclude-module "PySide6.QtMultimedia" `
    --exclude-module "PySide6.QtMultimediaWidgets" `
    --exclude-module "PySide6.QtNetwork" `
    --exclude-module "PySide6.QtNetworkAuth" `
    --exclude-module "PySide6.QtNfc" `
    --exclude-module "PySide6.QtPositioning" `
    --exclude-module "PySide6.QtQuick" `
    --exclude-module "PySide6.QtQuickWidgets" `
    --exclude-module "PySide6.QtRemoteObjects" `
    --exclude-module "PySide6.QtSensors" `
    --exclude-module "PySide6.QtSerialPort" `
    --exclude-module "PySide6.QtWebEngineCore" `
    --exclude-module "PySide6.QtWebEngineWidgets" `
    --exclude-module "PySide6.QtWebSockets" `
    --exclude-module "PySide6.QtXml" `
    --exclude-module "PySide6.QtXmlPatterns" `
    @mode `
    main.py

Write-Host "`n打包完成！" -ForegroundColor Green
Write-Host "目录模式: $ScriptDir\dist\ScoreReportTool\" -ForegroundColor Cyan
Write-Host "单文件模式: $ScriptDir\dist\ScoreReportTool.exe" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 优化建议：" -ForegroundColor Yellow
Write-Host "  - 使用 --OneFile 参数生成单文件EXE（自动压缩，体积更小）" -ForegroundColor Gray
Write-Host "  - 使用 --Optimize 参数启用代码优化" -ForegroundColor Gray
Write-Host "  - 将 node 文件夹放在 EXE 同目录可减少包体积约30MB" -ForegroundColor Gray
