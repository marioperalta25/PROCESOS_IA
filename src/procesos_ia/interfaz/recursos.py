"""Cargador de recursos gráficos e iconos locales para la interfaz."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap


class GestorRecursos:
    """Localiza y carga recursos visuales (iconos, emblemas) sin rutas absolutas fijas."""

    def __init__(self, directorio_base: Path | None = None) -> None:
        if directorio_base is not None:
            self._directorio_raiz = directorio_base
        else:
            # Subir desde src/procesos_ia/interfaz hasta la raiz del proyecto
            self._directorio_raiz = Path(__file__).resolve().parent.parent.parent.parent

        self._directorio_imagenes = self._directorio_raiz / "recursos" / "imagenes"

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
