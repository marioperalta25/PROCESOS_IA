"""Gestor persistente de rutas recientes para dialogos de seleccion de archivos."""

from __future__ import annotations

import os
from pathlib import Path
from PySide6.QtCore import QSettings

CLAVE_ULTIMA_CARPETA_IMAGENES = "rutas/ultima_carpeta_imagenes"
CLAVE_ULTIMO_ARCHIVO_TABULAR = "rutas/ultimo_archivo_tabular"
CLAVE_ULTIMA_CARPETA_SALIDA = "rutas/ultima_carpeta_salida"


class GestorRutasRecientes:
    """Conserva y recupera las ultimas rutas navegadas por el usuario en el sistema."""

    def __init__(self) -> None:
        self._settings = QSettings("PROCESOS_IA", "PROCESOS_IA")

    def obtener_ruta_imagenes(self, ruta_fallback: Path | str | None = None) -> str:
        """Devuelve la ultima carpeta de imagenes visitada o la ruta fallback si es valida."""
        guardada = self._settings.value(CLAVE_ULTIMA_CARPETA_IMAGENES, "")
        if guardada and Path(str(guardada)).is_dir():
            return str(guardada)
        if ruta_fallback and Path(str(ruta_fallback)).is_dir():
            return str(ruta_fallback)
        pictures = Path.home() / "Pictures"
        if pictures.is_dir():
            return str(pictures)
        return str(Path.home())

    def guardar_ruta_imagenes(self, ruta: Path | str) -> None:
        """Persiste la ultima carpeta de imagenes seleccionada."""
        p = Path(ruta)
        directorio = p if p.is_dir() else p.parent
        if directorio.is_dir():
            self._settings.setValue(CLAVE_ULTIMA_CARPETA_IMAGENES, str(directorio.resolve()))

    def obtener_ruta_tabular(self, ruta_fallback: Path | str | None = None) -> str:
        """Devuelve el ultimo directorio donde se abrio un archivo CSV o Excel."""
        guardada = self._settings.value(CLAVE_ULTIMO_ARCHIVO_TABULAR, "")
        if guardada and Path(str(guardada)).is_dir():
            return str(guardada)
        if ruta_fallback and Path(str(ruta_fallback)).is_dir():
            return str(ruta_fallback)
        documents = Path.home() / "Documents"
        if documents.is_dir():
            return str(documents)
        return str(Path.home())

    def guardar_ruta_tabular(self, ruta: Path | str) -> None:
        """Persiste el directorio del archivo tabular abierto."""
        p = Path(ruta)
        directorio = p if p.is_dir() else p.parent
        if directorio.is_dir():
            self._settings.setValue(CLAVE_ULTIMO_ARCHIVO_TABULAR, str(directorio.resolve()))

    def obtener_ruta_salida(self, ruta_fallback: Path | str | None = None) -> str:
        """Devuelve la ultima carpeta de salida seleccionada por el usuario."""
        guardada = self._settings.value(CLAVE_ULTIMA_CARPETA_SALIDA, "")
        if guardada and Path(str(guardada)).is_dir():
            return str(guardada)
        if ruta_fallback and Path(str(ruta_fallback)).is_dir():
            return str(ruta_fallback)
        return str(Path.home())

    def guardar_ruta_salida(self, ruta: Path | str) -> None:
        """Persiste la carpeta de salida elegida."""
        p = Path(ruta)
        directorio = p if p.is_dir() else p.parent
        if directorio.is_dir():
            self._settings.setValue(CLAVE_ULTIMA_CARPETA_SALIDA, str(directorio.resolve()))
