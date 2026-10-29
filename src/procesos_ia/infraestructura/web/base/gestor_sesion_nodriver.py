"""Gestor del ciclo de vida del navegador Chromium mediante Nodriver."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.controlador_ventana import (
    aplicar_modo_flotante_sin_foco,
)

logger = logging.getLogger(__name__)

try:
    import nodriver as uc

    NODRIVER_DISPONIBLE = True
except ImportError:
    NODRIVER_DISPONIBLE = False
    uc = None


class GestorSesionNodriver:
    """Administra el arranque, navegación y cierre seguro de Chromium persistente."""

    def __init__(self, configuracion: ConfiguracionWeb | None = None) -> None:
        self._config = configuracion or ConfiguracionWeb()
        self._navegador: Any | None = None
        self._pestana_activa: Any | None = None

    @property
    def configuracion(self) -> ConfiguracionWeb:
        return self._config

    @property
    def navegador(self) -> Any | None:
        return self._navegador

    @property
    def pestana_activa(self) -> Any | None:
        return self._pestana_activa

    async def iniciar_navegador(
        self,
        patrones_ventana: list[str] | tuple[str, ...] = ("Google Chrome", "Chromium"),
    ) -> Any:
        """Inicia el navegador persistente con limpieza de bloqueos previa."""
        if not NODRIVER_DISPONIBLE:
            raise RuntimeError(
                "[ERROR] nodriver no esta instalado en el entorno de ejecucion"
            )

        if self._navegador is not None:
            return self._navegador

        self._config.asegurar_directorios()
        self._config.limpiar_bloqueos_perfil()

        argumentos = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ]

        logger.info("[INFO] Iniciando sesion de navegador Nodriver...")
        try:
            self._navegador = await asyncio.wait_for(
                uc.start(
                    user_data_dir=str(self._config.directorio_perfil),
                    headless=False,
                    browser_args=argumentos,
                ),
                timeout=25.0,
            )
        except asyncio.TimeoutError:
            self._navegador = None
            raise RuntimeError(
                "[ERROR] Tiempo de espera agotado (25s) al iniciar el navegador Chromium. Verifique procesos huérfanos."
            )

        # Aplicar modo flotante sin foco tras el arranque
        await asyncio.sleep(1.0)
        aplicar_modo_flotante_sin_foco(patrones_ventana, self._config.ventana)

        return self._navegador

    async def navegar_o_reutilizar(
        self,
        url_destino: str,
        patrones_ventana: list[str] | tuple[str, ...],
    ) -> Any:
        """Abre o reutiliza una pestaña para la URL destino y posiciona la ventana."""
        navegador = await self.iniciar_navegador(patrones_ventana)

        if self._pestana_activa is None:
            self._pestana_activa = await navegador.get(url_destino)
        else:
            await self._pestana_activa.get(url_destino)

        await asyncio.sleep(2.0)
        aplicar_modo_flotante_sin_foco(patrones_ventana, self._config.ventana)
        return self._pestana_activa

    async def abrir_nueva_pestana(
        self,
        url_destino: str = "https://www.google.com",
        patrones_ventana: list[str] | tuple[str, ...] = ("Google Chrome", "Chromium"),
    ) -> Any:
        """Abre una nueva pestaña en el mismo navegador y perfil persistente."""
        navegador = await self.iniciar_navegador(patrones_ventana)
        try:
            pestana = await navegador.get(url_destino, new_tab=True)
        except Exception:
            pestana = await navegador.get(url_destino)

        await asyncio.sleep(2.0)
        aplicar_modo_flotante_sin_foco(patrones_ventana, self._config.ventana)
        return pestana

    async def cerrar(self) -> None:
        """Cierra el navegador de forma controlada y libera recursos."""
        if self._navegador is not None:
            proc = getattr(self._navegador, "_process", None)
            pid = getattr(proc, "pid", None) if proc else None
            try:
                if self._pestana_activa is not None:
                    try:
                        await self._pestana_activa.close()
                    except Exception:
                        pass
                conn = getattr(self._navegador, "connection", None)
                if conn is not None and hasattr(conn, "disconnect"):
                    try:
                        await conn.disconnect()
                    except Exception:
                        pass
                await asyncio.sleep(0.1)
                self._navegador.stop()
            except Exception as error:
                logger.warning(
                    "[ALERTA] Detencion de navegador con advertencia: %s", error
                )
            finally:
                if pid and os.name == "nt":
                    try:
                        import subprocess
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(pid)],
                            capture_output=True,
                            check=False,
                        )
                    except Exception:
                        pass
                self._navegador = None
                self._pestana_activa = None
                self._config.limpiar_bloqueos_perfil()
                self._config.limpiar_imagenes_temporales()
                logger.info("[INFO] Sesion de navegador cerrada correctamente.")

    async def cerrar_navegador(self) -> None:
        """Alias de compatibilidad para cerrar la sesion de navegador."""
        await self.cerrar()
