param(
    [string]$Version = "",
    [switch]$Verificar
)

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz

$RutaToml = Join-Path $Raiz "recursos\configuracion\navegador.toml"
if ([string]::IsNullOrWhiteSpace($Version)) {
    $Contenido = Get-Content $RutaToml -Raw -Encoding UTF8
    if ($Contenido -match 'aplicacion\s*=\s*"([^"]+)"') {
        $Version = $Matches[1]
    } else {
        $Version = "1.0.1"
    }
}

Write-Host "[INFO] Iniciando compilacion de PROCESOS_IA version $Version..."
python -m PyInstaller --noconfirm --clean (Join-Path $Raiz "PROCESOS_IA.spec")
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Fallo la compilacion con PyInstaller."
    exit 1
}

$Exe = Join-Path $Raiz "dist\PROCESOS_IA\PROCESOS_IA.exe"
if (-not (Test-Path $Exe)) {
    Write-Host "[ERROR] No se encontro el ejecutable generado en: $Exe"
    exit 1
}

if ($Verificar) {
    $Informe = Join-Path $Raiz "dist\informe_comprobacion.json"
    if (Test-Path $Informe) { Remove-Item $Informe -Force }
    Write-Host "[INFO] Ejecutando comprobacion de distribucion..."
    $Proc = Start-Process -FilePath $Exe -ArgumentList "--comprobar-distribucion", $Informe -PassThru
    if (-not $Proc.WaitForExit(120000)) {
        Stop-Process -Id $Proc.Id -Force -ErrorAction SilentlyContinue
        Write-Host "[ERROR] Tiempo de espera agotado (120s) en la comprobacion."
        exit 1
    }
    if ($Proc.ExitCode -ne 0 -or -not (Test-Path $Informe)) {
        Write-Host "[ERROR] La comprobacion fallo (codigo $($Proc.ExitCode))."
        exit 1
    }
}

$Iscc = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Iscc) {
    Write-Host "[ALERTA] No se encontro Inno Setup 6 (ISCC.exe). Solo se genero la version portable."
    Write-Host "[OK] Ejecutable portable: $Exe"
    exit 0
}

$Iss = Join-Path $PSScriptRoot "PROCESOS_IA.iss"
$TmpOut = Join-Path $env:TEMP "procesos_ia_setup_out"
New-Item -ItemType Directory -Force -Path $TmpOut | Out-Null
$NombreSetup = "PROCESOS_IA_Actualizacion_$Version.exe"
$DirInstaladores = Join-Path $Raiz "dist\instaladores"
New-Item -ItemType Directory -Force -Path $DirInstaladores | Out-Null
$Instalador = Join-Path $DirInstaladores $NombreSetup

Write-Host "[INFO] Generando instalador de actualizacion con Inno Setup..."
$CompiladoIss = $false
for ($intento = 1; $intento -le 2; $intento++) {
    & $Iscc "/DVersionApp=$Version" "/DRaizProyecto=$Raiz" "/O$TmpOut" $Iss
    if ($LASTEXITCODE -eq 0) { $CompiladoIss = $true; break }
    Write-Host "[ALERTA] Reintentando compilacion de instalador ($intento/2)..."
    Start-Sleep -Seconds 3
}
if (-not $CompiladoIss) {
    Write-Host "[ERROR] Fallo la compilacion del instalador Inno Setup."
    exit 1
}
Move-Item -Path (Join-Path $TmpOut $NombreSetup) -Destination $Instalador -Force

Write-Host ""
Write-Host "[OK] Compilacion completada."
Write-Host "[OK] Version: $Version (actualizacion compatible sobre instalacion previa)"
Write-Host "[OK] Ejecutable portable: $Exe"
Write-Host "[OK] Instalador de actualizacion: $Instalador"
