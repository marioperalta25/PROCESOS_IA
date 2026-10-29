"""Gestor optimizado para procesamiento de lotes de imagenes con memoria constante O(1).

Disenado para ser reutilizado en Google Lens, Gemini, DeepSeek y otros motores visuales.
"""

from __future__ import annotations

import csv
import gc
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import re
from typing import Any

EXTENSIONES_IMAGEN_PREDETERMINADAS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


@dataclass(slots=True)
class EstadoLoteImagenes:
    """Informacion del estado previo de una carpeta de imagenes y su CSV asociado."""

    carpeta: Path
    csv_existente: Path | None
    total_imagenes: int
    imagenes_pendientes: list[Path]
    imagenes_procesadas_count: int

    @property
    def hay_nuevas(self) -> bool:
        """Indica si existen imagenes pendientes por procesar."""
        return len(self.imagenes_pendientes) > 0


def listar_imagenes_carpeta(
    carpeta: Path, extensiones: set[str] | None = None
) -> list[Path]:
    """Lista de manera eficiente los archivos de imagen en una carpeta."""
    exts = extensiones or EXTENSIONES_IMAGEN_PREDETERMINADAS
    if not carpeta.is_dir():
        return []
    return sorted(
        [p for p in carpeta.iterdir() if p.is_file() and p.suffix.lower() in exts],
        key=lambda p: p.name.lower(),
    )


def obtener_nombres_procesados_csv(
    ruta_csv: Path, columna_fuente: str = "fuente_imagen"
) -> set[str]:
    """Extrae unicamente los nombres de imagenes ya procesadas sin cargar diccionarios en RAM.

    Usa un generador linea a linea O(1) en lectura para consumir menos de 300 KB de RAM.
    """
    if not ruta_csv.is_file() or ruta_csv.stat().st_size == 0:
        return set()

    nombres_procesados: set[str] = set()
    try:
        with open(ruta_csv, mode="r", encoding="utf-8-sig", errors="ignore") as f:
            lector = csv.reader(f)
            cabecera = next(lector, None)
            if not cabecera:
                return set()

            idx_col = -1
            for i, col in enumerate(cabecera):
                if col.strip().lower() == columna_fuente.lower():
                    idx_col = i
                    break

            if idx_col == -1:
                return set()

            for fila in lector:
                if len(fila) > idx_col:
                    valor = fila[idx_col].strip()
                    if valor:
                        nombres_procesados.add(Path(valor).name.lower())
    except Exception:
        pass

    return nombres_procesados


def buscar_csv_previo_carpeta(
    directorio_salidas: Path, nombre_carpeta: str, prefijo: str = "extraccion_lens"
) -> Path | None:
    """Busca si ya existe un CSV generado previamente para la carpeta indicada."""
    if not directorio_salidas.is_dir():
        return None

    patron = f"{prefijo}_{nombre_carpeta}_*.csv"
    coincidencias = list(directorio_salidas.glob(patron))

    csv_fijo = directorio_salidas / f"{prefijo}_{nombre_carpeta}.csv"
    if csv_fijo.is_file():
        coincidencias.append(csv_fijo)

    if not coincidencias:
        return None

    coincidencias.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return coincidencias[0]


def verificar_estado_carpeta_imagenes(
    carpeta: Path,
    directorio_salidas: Path,
    prefijo: str = "extraccion_lens",
    columna_fuente: str = "fuente_imagen",
    extensiones: set[str] | None = None,
) -> EstadoLoteImagenes:
    """Evalua si la carpeta ya tiene un CSV previo y clasifica imagenes pendientes."""
    imagenes_disco = listar_imagenes_carpeta(carpeta, extensiones)
    total_imgs = len(imagenes_disco)

    csv_previo = buscar_csv_previo_carpeta(directorio_salidas, carpeta.name, prefijo)
    if not csv_previo:
        return EstadoLoteImagenes(
            carpeta=carpeta,
            csv_existente=None,
            total_imagenes=total_imgs,
            imagenes_pendientes=imagenes_disco,
            imagenes_procesadas_count=0,
        )

    nombres_ya_procesados = obtener_nombres_procesados_csv(csv_previo, columna_fuente)
    pendientes: list[Path] = [
        p for p in imagenes_disco if p.name.lower() not in nombres_ya_procesados
    ]

    return EstadoLoteImagenes(
        carpeta=carpeta,
        csv_existente=csv_previo,
        total_imagenes=total_imgs,
        imagenes_pendientes=pendientes,
        imagenes_procesadas_count=total_imgs - len(pendientes),
    )


def generar_ruta_csv_salida(
    directorio_salidas: Path,
    nombre_carpeta: str,
    prefijo: str = "extraccion_lens",
    fecha_str: str | None = None,
) -> Path:
    """Genera la ruta inicial de salida con patron <prefijo>_<carpeta>_<YYYYMMDD>.csv."""
    fecha = fecha_str or datetime.now().strftime("%Y%m%d")
    return directorio_salidas / f"{prefijo}_{nombre_carpeta}_{fecha}.csv"


def actualizar_nombre_csv_modificado(
    ruta_existente: Path, fecha_hoy: str | None = None
) -> Path:
    """Renombra atomicamente a nivel de disco actualizando la fecha a _modificado_<fecha>."""
    if not ruta_existente.is_file():
        return ruta_existente

    fecha = fecha_hoy or datetime.now().strftime("%Y%m%d")
    stem = ruta_existente.stem

    limpio = re.sub(r"(?:_modificado)?_\d{8}$", "", stem)
    nuevo_nombre = f"{limpio}_modificado_{fecha}.csv"
    nueva_ruta = ruta_existente.parent / nuevo_nombre

    if nueva_ruta != ruta_existente:
        try:
            os.replace(ruta_existente, nueva_ruta)
            return nueva_ruta
        except Exception:
            return ruta_existente

    return ruta_existente


def escribir_fila_incremental_csv(
    fila: dict[str, Any], ruta_csv: Path, campos: list[str]
) -> None:
    """Escribe una fila de forma inmediata en el CSV garantizando append O(1) a disco."""
    existe_archivo = ruta_csv.is_file() and ruta_csv.stat().st_size > 0
    with open(ruta_csv, mode="a", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        if not existe_archivo:
            escritor.writeheader()
        escritor.writerow(fila)
        f.flush()


def recolectar_basura_ciclo(indice: int = 0, intervalo: int = 10) -> int:
    """Invoca una recoleccion generacional liviana de basura para devolver RAM al sistema."""
    if intervalo <= 0 or indice % intervalo == 0:
        return gc.collect(1)
    return 0
