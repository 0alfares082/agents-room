# Removes what scripts\install.ps1 set up: the Startup shortcut and the running board.
#
#   powershell -ExecutionPolicy Bypass -File scripts\uninstall.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Serve = Join-Path $Root "board\serve.py"
$Lnk = Join-Path ([Environment]::GetFolderPath("Startup")) "Agents Room Board.lnk"
if (Test-Path $Lnk) { Remove-Item $Lnk -Force }
Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" |
    Where-Object { $_.CommandLine -and $_.CommandLine.Contains($Serve) } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Write-Output "Agents room removed."
