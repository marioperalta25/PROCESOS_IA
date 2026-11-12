"""Controlador de ventana Win32 para posicionamiento flotante sin robo de foco."""

from __future__ import annotations

import logging
import sys
from typing import Callable

from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionVentanaWeb

logger = logging.getLogger(__name__)

try:
    import win32con
    import win32gui
    import win32process

    WIN32_DISPONIBLE = True
except ImportError:
    WIN32_DISPONIBLE = False


def es_plataforma_compatible() -> bool:
    """Verifica si el sistema operativo y librerías soportan Win32."""
    return sys.platform == "win32" and WIN32_DISPONIBLE


def obtener_pids_arbol(pid_raiz: int | None) -> set[int]:
    """Obtiene el conjunto de PIDs del proceso raiz y sus procesos hijos."""
    if not pid_raiz:
        return set()
    pids = {pid_raiz}
    try:
        import psutil

        padre = psutil.Process(pid_raiz)
        for hijo in padre.children(recursive=True):
            pids.add(hijo.pid)
    except Exception:
        pass
    return pids


def buscar_manejador_ventana(
    patrones_titulo: list[str] | tuple[str, ...],
    pid_esperado: int | None = None,
) -> int | None:
    """Busca el HWND de la ventana del navegador que coincida con patrones y PID."""
    if not es_plataforma_compatible():
        return None

    pids_permitidos = obtener_pids_arbol(pid_esperado) if pid_esperado else None
    patrones_normalizados = [p.lower() for p in patrones_titulo if p]
    coincidencia: list[int] = []

    def _evaluar_ventana(hwnd: int, _: int) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            if pids_permitidos is not None:
                try:
                    _, pid_win = win32process.GetWindowThreadProcessId(hwnd)
                    if pid_win not in pids_permitidos:
                        return True
                except Exception:
                    return True
            titulo = win32gui.GetWindowText(hwnd).lower()
            if not patrones_normalizados or any(patron in titulo for patron in patrones_normalizados):
                coincidencia.append(hwnd)
                return False
        return True

    try:
        win32gui.EnumWindows(_evaluar_ventana, 0)
    except Exception as error:
        logger.debug("[INFO] Busqueda de ventana completada con interrupcion: %s", error)

    return coincidencia[0] if coincidencia else None


def aplicar_modo_flotante_sin_foco(
    patrones_titulo: list[str] | tuple[str, ...],
    configuracion: ConfiguracionVentanaWeb | None = None,
    pid_esperado: int | None = None,
) -> bool:
    """Posiciona la ventana en modo flotante visible sin robar foco activo.

    Aplica las banderas HWND_TOPMOST y SWP_NOACTIVATE para mantener el
    navegador en segundo plano visual sin interrumpir la escritura del usuario.
    Solo afecta a ventanas que correspondan al proceso indicado por pid_esperado.
    """
    if not es_plataforma_compatible():
        logger.warning("[ALERTA] Win32 API no disponible en este entorno.")
        return False

    config = configuracion or ConfiguracionVentanaWeb()
    hwnd = buscar_manejador_ventana(patrones_titulo, pid_esperado=pid_esperado)
    if not hwnd:
        return False

    banderas = win32con.SWP_SHOWWINDOW
    if config.no_activar_foco:
        banderas |= win32con.SWP_NOACTIVATE

    posicion_z = win32con.HWND_TOPMOST if config.siempre_al_frente else win32con.HWND_NOTOPMOST

    try:
        win32gui.SetWindowPos(
            hwnd,
            posicion_z,
            config.x,
            config.y,
            config.ancho,
            config.alto,
            banderas,
        )
        return True
    except Exception as error:
        logger.error("[ERROR] Fallo al posicionar ventana Win32: %s", error)
        return False
