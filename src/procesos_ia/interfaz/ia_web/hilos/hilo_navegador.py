"""Hilo para abrir el navegador respetando la configuracion compartida."""

from __future__ import annotations

import asyncio
from PySide6.QtCore import QObject, QThread, Signal

from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.infraestructura.web.base.lanzador_manual import lanzar_navegador_manual
from procesos_ia.infraestructura.web.base.parametros_navegador import parametros_navegador


class HiloLanzarNavegador(QThread):
    """Abre el perfil del usuario y comunica si no pudo aplicar la politica de ventana."""

    senial_exito = Signal(str)
    senial_error = Signal(str)

    def __init__(self, url_destino: str, configuracion: ConfiguracionWeb | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._url = url_destino
        self._config = configuracion or ConfiguracionWeb()

    def run(self) -> None:
        parametros = parametros_navegador()
        try:
            self._config.asegurar_directorios()
            self._config.limpiar_bloqueos_perfil()
            pid = lanzar_navegador_manual(self._url, self._config)
            if pid is not None:
                self.senial_exito.emit(parametros["mensajes"]["abierto"].format(pid=pid))
                return

            async def abrir() -> None:
                gestor = GestorSesionNodriver(self._config)
                await gestor.navegar_o_reutilizar(self._url, parametros["patrones_titulo"])

            asyncio.run(abrir())
            self.senial_exito.emit(self._url)
        except Exception as error:
            self.senial_error.emit(parametros["mensajes"]["error_inicio"].format(causa=error))
