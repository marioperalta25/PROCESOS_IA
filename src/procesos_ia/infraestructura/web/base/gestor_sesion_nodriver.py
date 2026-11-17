"""Gestor del ciclo de vida del navegador Chromium mediante Nodriver."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
import subprocess
from typing import Any

from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.controlador_ventana import (
    aplicar_ventana_con_reintentos,
    obtener_ventana_activa,
)

from procesos_ia.infraestructura.web.base.parametros_navegador import argumentos_navegador, parametros_navegador

logger = logging.getLogger(__name__)

try:
    import nodriver as uc

    NODRIVER_DISPONIBLE = True
except ImportError:
    NODRIVER_DISPONIBLE = False
    uc = None


def terminar_arbol_procesos(pid_padre: int | None) -> int:
    """Termina de forma forzada e inmediata un proceso y todos sus procesos hijos."""
    if not pid_padre:
        return 0
    terminados = 0
    try:
        import psutil

        padre = psutil.Process(pid_padre)
        hijos = padre.children(recursive=True)
        for hijo in hijos:
            try:
                hijo.kill()
                terminados += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        try:
            padre.kill()
            terminados += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    except Exception as error:
        logger.debug("[INFO] Proceso padre %s ya finalizado o inaccesible: %s", pid_padre, error)

    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid_padre)],
                capture_output=True,
                check=False,
                timeout=3.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass

    return terminados


class GestorSesionNodriver:
    """Administra el arranque, navegación y cierre seguro de Chromium persistente."""

    def __init__(self, configuracion: ConfiguracionWeb | None = None) -> None:
        self._config = configuracion or ConfiguracionWeb()
        self._navegador: Any | None = None
        self._pestana_activa: Any | None = None
        self._pid_navegador: int | None = None
        self._ventana_aplicada: Any | None = None
        self.ultimo_aviso_ventana: str | None = None

    def actualizar_configuracion(self, configuracion: ConfiguracionWeb) -> None:
        if self._navegador is not None and configuracion.directorio_perfil != self._config.directorio_perfil:
            raise ValueError(parametros_navegador()["mensajes"]["perfil_activo"])
        self._config = configuracion

    async def _aplicar_ventana(self, patrones: list[str] | tuple[str, ...], hwnd_foco_previo: int | None = None) -> None:
        aplicado = await asyncio.to_thread(
            aplicar_ventana_con_reintentos, patrones, self._config.ventana,
            self._pid_navegador, self._config.directorio_perfil, hwnd_foco_previo,
        )
        if not aplicado:
            aviso = parametros_navegador()["mensajes"]["ventana_no_aplicada"]
            self.ultimo_aviso_ventana = aviso
            logger.warning(aviso)
        else:
            self.ultimo_aviso_ventana = None
            self._ventana_aplicada = self._config.ventana

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
        patrones_ventana: list[str] | tuple[str, ...] | None = None,
    ) -> Any:
        """Inicia el navegador persistente con limpieza de bloqueos previa."""
        if not NODRIVER_DISPONIBLE:
            raise RuntimeError(
                "[ERROR] nodriver no esta instalado en el entorno de ejecucion"
            )

        patrones = tuple(parametros_navegador()["patrones_titulo"]) if patrones_ventana is None else patrones_ventana
        if self._navegador is not None:
            if self._ventana_aplicada != self._config.ventana:
                await self._aplicar_ventana(patrones)
            return self._navegador

        self._config.asegurar_directorios()
        self._config.limpiar_bloqueos_perfil()

        argumentos = argumentos_navegador(self._config)
        hwnd_previo = obtener_ventana_activa() if self._config.ventana.no_activar_foco else None

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

        proc = getattr(self._navegador, "_process", None)
        self._pid_navegador = getattr(proc, "pid", None) if proc else None

        # Aplicar modo flotante sin foco tras el arranque
        await asyncio.sleep(1.0)
        await self._aplicar_ventana(patrones, hwnd_foco_previo=hwnd_previo)

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

        await asyncio.sleep(0.5)
        await self._aplicar_ventana(patrones_ventana)
        return self._pestana_activa

    async def abrir_nueva_pestana(
        self,
        url_destino: str = "https://www.google.com",
        patrones_ventana: list[str] | tuple[str, ...] | None = None,
    ) -> Any:
        """Abre una nueva pestaña en el mismo navegador y perfil persistente."""
        patrones = tuple(parametros_navegador()["patrones_titulo"]) if patrones_ventana is None else patrones_ventana
        navegador = await self.iniciar_navegador(patrones)
        try:
            pestana = await navegador.get(url_destino, new_tab=True)
        except Exception:
            pestana = await navegador.get(url_destino)

        await asyncio.sleep(0.5)
        await self._aplicar_ventana(patrones)
        return pestana

    async def cerrar(self) -> None:
        """Cierra el navegador de forma controlada y libera recursos con timeout estricto."""
        if self._navegador is not None:
            proc = getattr(self._navegador, "_process", None)
            pid = getattr(proc, "pid", None) if proc else None
            try:
                if self._pestana_activa is not None:
                    try:
                        await asyncio.wait_for(self._pestana_activa.close(), timeout=0.8)
                    except Exception:
                        pass
                conn = getattr(self._navegador, "connection", None)
                if conn is not None and hasattr(conn, "disconnect"):
                    try:
                        await asyncio.wait_for(conn.disconnect(), timeout=0.8)
                    except Exception:
                        pass
                await asyncio.sleep(0.05)
                try:
                    self._navegador.stop()
                except Exception:
                    pass
            except Exception as error:
                logger.warning(
                    "[ALERTA] Detencion de navegador con advertencia: %s", error
                )
            finally:
                pid_a_cerrar = pid or self._pid_navegador
                terminar_arbol_procesos(pid_a_cerrar)
                if isinstance(proc, asyncio.subprocess.Process):
                    try:
                        await asyncio.wait_for(proc.communicate(), parametros_navegador()["tiempo_cierre_segundos"])
                    except (OSError, ValueError, asyncio.TimeoutError):
                        pass
                self._navegador = None
                self._pestana_activa = None
                self._pid_navegador = None
                self._config.limpiar_bloqueos_perfil()
                self._config.limpiar_imagenes_temporales()
                logger.info("[INFO] Sesion de navegador cerrada correctamente.")

    def forzar_cierre_inmediato(self) -> None:
        """Termina los procesos inmediatamente y limpia referencias para evitar llamadas CDP pendientes."""
        pid = self._pid_navegador
        if self._navegador is not None:
            proc = getattr(self._navegador, "_process", None)
            pid = getattr(proc, "pid", None) if proc else pid
        self._navegador = None
        self._pestana_activa = None
        self._pid_navegador = None
        terminar_arbol_procesos(pid)
        self._config.limpiar_bloqueos_perfil()

    async def cerrar_navegador(self) -> None:
        """Alias de compatibilidad para cerrar la sesion de navegador."""
        await self.cerrar()

    async def reiniciar_con_perfil_limpio(self) -> None:
        """Cierra el navegador, purga el perfil en disco y elimina bloqueos."""
        await self.cerrar()
        await asyncio.sleep(0.3)
        self._config.purgar_perfil_usuario()
        self._config.limpiar_bloqueos_perfil()
