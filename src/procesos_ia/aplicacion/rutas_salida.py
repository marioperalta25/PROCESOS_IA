"""Resolución y gestión de subcarpetas de salida por archivo de entrada."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re


def sanitizar_nombre_subcarpeta(nombre: str) -> str:
    """Sanitiza el nombre del archivo para su uso seguro como nombre de subcarpeta."""
    limpio = re.sub(r'[^\w\-.]', '_', nombre).strip('._ ')
    return limpio or "trabajo"


def es_subcarpeta_completada(carpeta: Path) -> bool:
    """Verifica si la subcarpeta ya contiene un procesamiento finalizado o con datos."""
    if not carpeta.is_dir():
        return False
    # Si existe marca explicita de completado
    if (carpeta / "completado.json").is_file():
        return True
    # Si existe archivo de resultado final consolidado con datos
    for nombre in ("resultado_procesado.csv", "resultado_procesado.xlsx"):
        archivo = carpeta / nombre
        if archivo.is_file() and archivo.stat().st_size > 0:
            return True
    return False


def resolver_ruta_disponible(directorio_destino: Path) -> Path:
    """Si el directorio ya existe y está completado, retorna el siguiente copia_n."""
    if not es_subcarpeta_completada(directorio_destino):
        return directorio_destino

    nombre_base = directorio_destino.name
    match_copia = re.match(r"^(.*?)(?:_copia_(\d+))?$", nombre_base)
    if match_copia and match_copia.group(2):
        base = match_copia.group(1)
        inicio = int(match_copia.group(2)) + 1
    else:
        base = nombre_base
        inicio = 1

    indice = inicio
    while True:
        candidato = directorio_destino.parent / f"{base}_copia_{indice}"
        if not es_subcarpeta_completada(candidato):
            return candidato
        indice += 1


def resolver_subcarpeta_salida(
    directorio_base: Path,
    ruta_entrada: Path,
    fecha_hoy: str | None = None,
) -> Path:
    """Asigna o recupera la subcarpeta de salida para un archivo de entrada dado.

    Si existe una subcarpeta previa en progreso (no completada), se reutiliza
    para permitir reanudación de progreso sin duplicar directorios.
    Si la subcarpeta ya existe y está completada (o si se procesa el archivo
    por segunda vez), se genera automáticamente el patrón copia_1, copia_2, etc.
    """
    nombre_base = sanitizar_nombre_subcarpeta(ruta_entrada.stem)
    fecha = fecha_hoy or datetime.now().strftime("%Y%m%d")

    candidato_fecha = directorio_base / f"{nombre_base}_{fecha}"

    if directorio_base.exists():
        coincidencias = [
            d for d in directorio_base.glob(f"{nombre_base}_*")
            if d.is_dir()
        ]
        if (directorio_base / nombre_base).is_dir():
            coincidencias.append(directorio_base / nombre_base)

        if coincidencias:
            coincidencias.sort(key=lambda d: d.stat().st_mtime, reverse=True)
            for sub in coincidencias:
                # Si hay una subcarpeta previa en progreso (no completada), reutilizarla para reanudar
                if not es_subcarpeta_completada(sub):
                    return sub

    return resolver_ruta_disponible(candidato_fecha)
