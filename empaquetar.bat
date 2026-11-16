@echo off
setlocal
if "%~1"=="" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0empaquetado\compilar.ps1"
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0empaquetado\compilar.ps1" -Version "%~1"
)
if errorlevel 1 (
    echo [ERROR] No se genero un instalador verificado. Revise el informe de compilacion.
    pause
    exit /b 1
)
pause
