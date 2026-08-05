$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Find-PythonCommand {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        & python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return @("python")
        }
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        & py -3.10 -c "import sys" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return @("py", "-3.11")
        }

        & py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return @("py", "-3")
        }
    }

    throw "未找到 Python 3.10 或更高版本。请安装 Python，并勾选 Add Python to PATH。"
}

$pythonCommand = Find-PythonCommand
$pythonExe = $pythonCommand[0]
$pythonArgs = @()
if ($pythonCommand.Count -gt 1) {
    $pythonArgs = $pythonCommand[1..($pythonCommand.Count - 1)]
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[LifeGraph] 正在创建 Python 虚拟环境..."
    & $pythonExe @pythonArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        throw "无法创建虚拟环境。"
    }
}

Write-Host "[LifeGraph] 正在安装/检查依赖..."
& .\.venv\Scripts\python.exe -m pip install -U pip | Out-Null
if ($LASTEXITCODE -ne 0) { throw "pip 更新失败" }

& .\.venv\Scripts\python.exe -m pip install -e .
if ($LASTEXITCODE -ne 0) { throw "依赖安装失败" }

Write-Host "[LifeGraph] 启动地址：http://127.0.0.1:8765"
& .\.venv\Scripts\python.exe scripts\run_dev.py
