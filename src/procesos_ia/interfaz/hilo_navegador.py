"""Hilo de segundo plano para abrir sesiones de navegador Chromium con Nodriver."""

from __future__ import annotations

import asyncio
import logging
from PySide6.QtCore import QObject, QThread, Signal

from procesos_ia.infraestructura.web.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.gestor_sesion_nodriver import (
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
