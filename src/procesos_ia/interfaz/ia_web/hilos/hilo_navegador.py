"""Hilo de segundo plano para abrir sesiones de navegador Chromium con Nodriver."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal

from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import (
    NODRIVER_DISPONIBLE,
    GestorSesionNodriver,
)

logger = logging.getLogger(__name__)


class HiloLanzarNavegador(QThread):
    """Abre el navegador interactivo con el perfil persistente configurado."""

    senial_exito = Signal(str)
    senial_error = Signal(str)

    def __init__(
        self,
        url_destino: str,
        configuracion: ConfiguracionWeb | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._url = url_destino
        self._config = configuracion or ConfiguracionWeb()

    def run(self) -> None:
        self._config.asegurar_directorios()
        self._config.limpiar_bloqueos_perfil()

        try:
            import nodriver.core.config as c
            chrome_exe = c.find_chrome_executable()
        except Exception:
            chrome_exe = None

        if chrome_exe and Path(chrome_exe).is_file():
            try:
                import subprocess
                args = [
                    str(chrome_exe),
                    f"--user-data-dir={self._config.directorio_perfil}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    self._url,
                ]
                proc = subprocess.Popen(args)
                self.senial_exito.emit(f"Navegador abierto en {self._url} (PID: {proc.pid})")
                return
            except Exception as e_sub:
                logger.debug("[INFO] Fallo lanzamiento directo, intentando con nodriver: %s", e_sub)

        if not NODRIVER_DISPONIBLE:
            self.senial_error.emit("Nodriver no esta instalado en el entorno de Python.")
            return

        async def _abrir() -> None:
            gestor = GestorSesionNodriver(self._config)
            patrones = ("Google Chrome", "Chromium", "DeepSeek", "Gemini")
            await gestor.navegar_o_reutilizar(self._url, patrones)

        try:
            asyncio.run(_abrir())
            self.senial_exito.emit(f"Navegador abierto en {self._url}")
        except Exception as error:
            logger.warning("[ALERTA] No se pudo abrir la sesion de navegador: %s", error)
            self.senial_error.emit(f"Error al abrir navegador: {error}")
