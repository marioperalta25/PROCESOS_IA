"""Controlador de ventana Win32 para posicionamiento flotante sin robo de foco."""

from __future__ import annotations

import logging
import sys
import time
import os
from pathlib import Path

from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionVentanaWeb

logger = logging.getLogger(__name__)


def _pertenece_al_perfil(pid: int, directorio: Path) -> bool:
    """Chrome puede delegar el lanzamiento a un proceso anterior del mismo perfil."""
    try:
        import psutil
    except ImportError:
        return False
    try:
        argumentos = psutil.Process(pid).cmdline()
        for indice, argumento in enumerate(argumentos):
            if argumento.startswith("--user-data-dir="):
                ruta = argumento.partition("=")[2].strip('"')
            elif argumento == "--user-data-dir" and indice + 1 < len(argumentos):
                ruta = argumentos[indice + 1].strip('"')
            else:
                continue
            return os.path.normcase(str(Path(ruta).resolve())) == os.path.normcase(str(directorio.resolve()))
    except (OSError, psutil.Error):
        return False
    return False

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
    directorio_perfil: Path | None = None,
) -> int | None:
    """Busca el HWND de la ventana del navegador que coincida con patrones y PID."""
    if not es_plataforma_compatible():
        return None

    pids_permitidos = obtener_pids_arbol(pid_esperado) if pid_esperado else None
    patrones_normalizados = [p.lower() for p in patrones_titulo if p]
    coincidencia: list[int] = []

    def _evaluar_ventana(hwnd: int, _: int) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            if pids_permitidos is not None or directorio_perfil is not None:
                try:
                    _, pid_win = win32process.GetWindowThreadProcessId(hwnd)
                    es_pid = pids_permitidos is not None and pid_win in pids_permitidos
                    es_perfil = directorio_perfil is not None and _pertenece_al_perfil(pid_win, directorio_perfil)
                    if not es_pid and not es_perfil:
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


def _restaurar_si_necesario(hwnd: int) -> None:
    """Restaura ventanas minimizadas o maximizadas sin robar el foco activo."""
    try:
        minimizada = bool(win32gui.IsIconic(hwnd))
        maximizada = win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMAXIMIZED
        if minimizada or maximizada:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
    except Exception:
        pass


def obtener_ventana_activa() -> int | None:
    """Devuelve el HWND de la ventana activa actual en Windows, si existe."""
    if not es_plataforma_compatible():
        return None
    try:
        hwnd = win32gui.GetForegroundWindow()
        return hwnd if hwnd else None
    except Exception:
        return None


def _restaurar_foco_previo(hwnd_navegador: int, hwnd_previo: int | None) -> None:
    """Devuelve el foco a la ventana previa solo si el navegador lo robo al abrirse."""
    if not hwnd_previo or hwnd_previo == hwnd_navegador:
        return
    try:
        if win32gui.GetForegroundWindow() == hwnd_navegador and win32gui.IsWindow(hwnd_previo):
            win32gui.SetForegroundWindow(hwnd_previo)
    except Exception:
        pass


def aplicar_modo_flotante_sin_foco(
    patrones_titulo: list[str] | tuple[str, ...],
    configuracion: ConfiguracionVentanaWeb | None = None,
    pid_esperado: int | None = None,
    directorio_perfil: Path | None = None,
    hwnd_foco_previo: int | None = None,
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
    hwnd = buscar_manejador_ventana(patrones_titulo, pid_esperado, directorio_perfil)
    if not hwnd:
        return False


    # La ventana ya es visible: volver a mostrarla puede restablecer su orden en Chrome.
    banderas = win32con.SWP_NOOWNERZORDER
    if config.no_activar_foco:
        banderas |= win32con.SWP_NOACTIVATE

    posicion_z = win32con.HWND_TOPMOST if config.siempre_al_frente else win32con.HWND_NOTOPMOST

    try:
        _restaurar_si_necesario(hwnd)
        win32gui.SetWindowPos(
            hwnd,
            posicion_z,
            config.x,
            config.y,
            config.ancho,
            config.alto,
            banderas,
        )
        estilo = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if config.no_activar_foco:
            _restaurar_foco_previo(hwnd, hwnd_foco_previo)
        return bool(estilo & win32con.WS_EX_TOPMOST) == config.siempre_al_frente
    except Exception as error:
        logger.error("[ERROR] Fallo al posicionar ventana Win32: %s", error)
        return False


def aplicar_ventana_con_reintentos(
    patrones: list[str] | tuple[str, ...], configuracion: ConfiguracionVentanaWeb,
    pid_esperado: int | None, directorio_perfil: Path, hwnd_foco_previo: int | None = None,
) -> bool:
    """Espera de forma acotada la ventana propia; no modifica navegadores personales."""
    from procesos_ia.infraestructura.web.base.parametros_navegador import parametros_navegador
    parametros = parametros_navegador()
    limite = time.monotonic() + parametros["tiempo_posicion_segundos"]
    confirmaciones = 0
    while True:
        if aplicar_modo_flotante_sin_foco(patrones, configuracion, pid_esperado, directorio_perfil, hwnd_foco_previo):
            confirmaciones += 1
            if confirmaciones >= parametros["confirmaciones_posicion"]:
                return True
        else:
            confirmaciones = 0
        if not es_plataforma_compatible() or time.monotonic() >= limite:
            return False
        time.sleep(parametros["intervalo_posicion_segundos"])
