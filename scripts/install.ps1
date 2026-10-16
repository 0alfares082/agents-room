# Installs the agents room on Windows: starts the board now and again at every login
# (a shortcut in your Startup folder). Board: http://127.0.0.1:8795
#
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
#
# Run it again any time; it replaces its own setup. scripts\uninstall.ps1 removes everything.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Port = 8795
$Serve = Join-Path $Root "board\serve.py"
$Logs = Join-Path $env:LOCALAPPDATA "agents-room"
$Lnk = Join-Path ([Environment]::GetFolderPath("Startup")) "Agents Room Board.lnk"

function Find-Python {
    # "py -3" first: the "python" name can be the Microsoft Store placeholder
    foreach ($cand in @(@("py", "-3"), @("python"), @("python3"))) {
        $exe = $cand[0]
        $extra = @()
        if ($cand.Count -gt 1) { $extra = $cand[1..($cand.Count - 1)] }
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        try {
            $out = @(& $exe @extra -c "import sys; print(sys.executable); print(sys.version_info >= (3, 9))" 2>$null)
        } catch { continue }
        if ($LASTEXITCODE -eq 0 -and $out.Count -ge 2) {
            if ($out[1].Trim() -ne "True") { throw "Python is older than 3.9. Install a newer one from https://www.python.org" }
            return $out[0].Trim()
        }
    }
    throw "Python 3.9 or newer is missing. Install it from https://www.python.org and tick 'Add python.exe to PATH'."
}

function Stop-Board {
    Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" |
        Where-Object { $_.CommandLine -and $_.CommandLine.Contains($Serve) } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

$Python = Find-Python
$PythonW = Join-Path (Split-Path $Python) "pythonw.exe"
if (-not (Test-Path $PythonW)) { $PythonW = $Python }

Stop-Board
Start-Sleep -Seconds 1

# another program on the port would answer the check below and hide a failed start
& $Python -c "import socket, sys`ntry:`n    socket.create_connection(('127.0.0.1', $Port), timeout=1).close()`nexcept OSError:`n    sys.exit(1)`nsys.exit(0)"
if ($LASTEXITCODE -eq 0) { throw "Port $Port is already used by another program. Stop it, then run this script again." }

New-Item -ItemType Directory -Force -Path $Logs | Out-Null
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($Lnk)
$link.TargetPath = $PythonW
$link.Arguments = "`"$Serve`" --port $Port"
$link.WorkingDirectory = $Root
$link.WindowStyle = 7
$link.Description = "Agents room board on http://127.0.0.1:$Port"
$link.Save()

$env:PYTHONDONTWRITEBYTECODE = "1"
Start-Process -FilePath $Python -ArgumentList @("`"$Serve`"", "--port", "$Port") -WorkingDirectory $Root `
    -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Logs "server.out.log") `
    -RedirectStandardError (Join-Path $Logs "server.err.log")

$ok = $false
for ($i = 0; $i -lt 20; $i++) {
    try {
        Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 "http://127.0.0.1:$Port/api/board" | Out-Null
        $ok = $true
        break
    } catch { Start-Sleep -Seconds 1 }
}
if (-not $ok) { throw "The board did not answer. Look at $Logs\server.err.log" }
Write-Output "Board running: http://127.0.0.1:$Port/   (show mode: http://127.0.0.1:$Port/?show=1)"
Write-Output "It starts again at every login (shortcut: $Lnk)."
