"""Enrutador centralizado de rutas y subcarpetas para modulos de PROCESOS_IA."""

from __future__ import annotations

import os
from pathlib import Path
import shutil

from procesos_ia.aplicacion.rutas_salida import (
    resolver_ruta_disponible,
    resolver_subcarpeta_salida,
    sanitizar_nombre_subcarpeta,
)


def obtener_directorio_raiz_predeterminado() -> Path:
    """Obtiene el directorio base central desde variable de entorno o escritorio."""
    ruta_env = os.environ.get("PROCESOS_IA_SALIDAS_DIR") or os.environ.get("PROCESOS_IA_BASE_DIR")
    if ruta_env:
        return Path(ruta_env)
    candidato_existente = Path.home() / "Desktop" / "procesos_ia_salidas"
    if candidato_existente.exists():
        return candidato_existente
    return Path.home() / "Desktop" / "PROCESOS_IA_SALIDAS"


class EnrutadorSalidas:
    """Gestiona la jerarquia centralizada de rutas de salida para todos los modulos.

    Estructura jerarquica generada:
    <directorio_raiz>/
        ├── plantillas/        (prompts y plantillas reutilizables .md)
        ├── analisis/          (procesamiento masivo y enriquecimiento de datos)
        │     └── <archivo>_<fecha>[_copia_n]/
        ├── conversaciones/    (historial y estado de chats locales)
        ├── extracciones/      (extracciones web y analisis de documentos)
        ├── reportes/          (informes ejecutivos y consolidados)
        └── temporales/        (capturas y cache de trabajo temporal)
    """

    def __init__(self, directorio_raiz: Path | None = None) -> None:
        self._raiz = (
            Path(directorio_raiz)
            if directorio_raiz is not None
            else obtener_directorio_raiz_predeterminado()
        )

    @property
    def raiz(self) -> Path:
        """Ruta al directorio central base de todas las salidas."""
        return self._raiz

    @property
    def datos(self) -> Path:
        """Subcarpeta central para archivos tabulares y datos de entrada."""
        return self._raiz / "datos"

    @property
    def imagenes(self) -> Path:
        """Subcarpeta central para imágenes de entrada y procesamiento visual."""
        return self._raiz / "imagenes"

    @property
    def plantillas(self) -> Path:
        """Subcarpeta central para plantillas de prompts de evaluacion."""
        return self._raiz / "plantillas"

    @property
    def analisis(self) -> Path:
        """Subcarpeta central para evaluaciones y enriquecimiento tabular."""
        return self._raiz / "analisis"

    @property
    def conversaciones(self) -> Path:
        """Subcarpeta central para historiales de chat y conversaciones."""
        return self._raiz / "conversaciones"

    @property
    def extracciones(self) -> Path:
        """Subcarpeta central para procesos de extraccion y navegacion web."""
        return self._raiz / "extracciones"

    @property
    def reportes(self) -> Path:
        """Subcarpeta central para reportes y exportaciones analiticas."""
        return self._raiz / "reportes"

    @property
    def temporales(self) -> Path:
        """Subcarpeta central para archivos temporales y capturas."""
        return self._raiz / "temporales"

    def establecer_directorio_raiz(self, nueva_raiz: Path) -> None:
        """Actualiza el directorio raíz y garantiza la estructura de subcarpetas."""
        self._raiz = Path(nueva_raiz)
        self.asegurar_directorios()

    def asegurar_directorios(self) -> None:
        """Crea la estructura base de directorios si todavia no existe."""
        for destino in (
            self._raiz,
            self.datos,
            self.imagenes,
            self.plantillas,
            self.analisis,
            self.conversaciones,
            self.extracciones,
            self.reportes,
            self.temporales,
        ):
            destino.mkdir(parents=True, exist_ok=True)

    def migrar_plantillas_previas(
        self, directorio_previo: Path | None = None
    ) -> list[Path]:
        """Copia plantillas de la ubicacion anterior hacia la nueva subcarpeta plantillas."""
        origen = directorio_previo or (Path.home() / "Desktop" / "procesos_ia_prompts")
        if not origen.is_dir():
            return []

        self.plantillas.mkdir(parents=True, exist_ok=True)
        migrados: list[Path] = []
        for archivo in origen.glob("*.md"):
            destino = self.plantillas / archivo.name
            if not destino.exists():
                shutil.copy2(archivo, destino)
                migrados.append(destino)
        return migrados

    def resolver_subcarpeta_analisis(
        self, ruta_entrada: Path, fecha_hoy: str | None = None
    ) -> Path:
        """Resuelve el subdirectorio para un archivo dentro de la subcarpeta analisis."""
        self.analisis.mkdir(parents=True, exist_ok=True)
        return resolver_subcarpeta_salida(self.analisis, ruta_entrada, fecha_hoy=fecha_hoy)

    def obtener_subcarpeta_modulo(self, modulo: str) -> Path:
        """Obtiene o crea una subcarpeta para un modulo nuevo dentro de la raiz."""
        nombre_limpio = sanitizar_nombre_subcarpeta(modulo)
        subcarpeta = self._raiz / nombre_limpio
        subcarpeta.mkdir(parents=True, exist_ok=True)
        return subcarpeta

    def resolver_subcarpeta_modulo(
        self, modulo: str, nombre_trabajo: str, fecha_hoy: str | None = None
    ) -> Path:
        """Resuelve un subdirectorio aislado para una corrida de cualquier modulo."""
        base_modulo = self.obtener_subcarpeta_modulo(modulo)
        return resolver_subcarpeta_salida(
            base_modulo, Path(nombre_trabajo), fecha_hoy=fecha_hoy
        )
