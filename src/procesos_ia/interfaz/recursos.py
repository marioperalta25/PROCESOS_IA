"""Cargador de recursos gráficos e iconos locales para la interfaz."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap

from procesos_ia.aplicacion.comun.localizador_recursos import obtener_ruta_recurso


class GestorRecursos:
    """Localiza y carga recursos visuales (iconos, emblemas) sin rutas absolutas fijas."""

    def __init__(self, directorio_base: Path | None = None) -> None:
        if directorio_base is not None:
            self._directorio_imagenes = directorio_base / "imagenes"
        else:
            self._directorio_imagenes = obtener_ruta_recurso("imagenes")

    @property
    def ruta_icono_aplicacion(self) -> Path:
        return self._directorio_imagenes / "icono-aplicacion.ico"

    @property
    def ruta_emblema_dragon(self) -> Path:
        return self._directorio_imagenes / "icono-dragon-sol.png"

    def obtener_icono_aplicacion(self) -> QIcon:
        """Devuelve el QIcon principal de la aplicación con sus variantes de resolución."""
        icono = QIcon()
        if self.ruta_icono_aplicacion.is_file():
            icono.addFile(str(self.ruta_icono_aplicacion))
        if self.ruta_emblema_dragon.is_file():
            icono.addFile(str(self.ruta_emblema_dragon))
        return icono

    def obtener_pixmap_emblema(self, ancho: int = 48, alto: int = 48) -> QPixmap:
        """Devuelve el emblema del dragón escalado de forma nítida."""
        ruta = self.ruta_emblema_dragon
        if ruta.is_file():
            pix = QPixmap(str(ruta))
            if not pix.isNull():
                return pix.scaled(
                    ancho,
                    alto,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        return QPixmap(ancho, alto)
