"""Controlador de ventana Win32 para posicionamiento flotante sin robo de foco."""

from __future__ import annotations

import logging
import sys
from typing import Callable

from procesos_ia.infraestructura.web.configuracion_web import ConfiguracionVentanaWeb

logger = logging.getLogger(__name__)

try:
    import win32con
    import win32gui

    WIN32_DISPONIBLE = True
except ImportError:
    WIN32_DISPONIBLE = False


def es_plataforma_compatible() -> bool:
    """Verifica si el sistema operativo y librerías soportan Win32."""
    return sys.platform == "win32" and WIN32_DISPONIBLE


def buscar_manejador_ventana(
    patrones_titulo: list[str] | tuple[str, ...],
) -> int | None:
    """Busca el HWND de la ventana que coincida con alguno de los patrones de texto."""
    if not es_plataforma_compatible():
        return None

    patrones_normalizados = [p.lower() for p in patrones_titulo if p]
    coincidencia: list[int] = []

    def _evaluar_ventana(hwnd: int, _: int) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            titulo = win32gui.GetWindowText(hwnd).lower()
            if titulo and any(patron in titulo for patron in patrones_normalizados):
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
) -> bool:
    """Posiciona la ventana en modo flotante visible sin robar foco activo.

    Aplica las banderas HWND_TOPMOST y SWP_NOACTIVATE para mantener el
    navegador en segundo plano visual sin interrumpir la escritura del usuario.
    """
    if not es_plataforma_compatible():
        logger.warning("[ALERTA] Win32 API no disponible en este entorno.")
        return False

    config = configuracion or ConfiguracionVentanaWeb()
    hwnd = buscar_manejador_ventana(patrones_titulo)
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
