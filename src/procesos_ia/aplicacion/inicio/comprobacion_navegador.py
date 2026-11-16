"""Comprueba un Chrome propio y temporal, sin cuentas ni consultas a servicios de IA."""

import asyncio
from pathlib import Path

from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb, ConfiguracionVentanaWeb
from procesos_ia.infraestructura.web.base.controlador_ventana import buscar_manejador_ventana, es_plataforma_compatible
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver


async def comprobar_navegador(raiz: Path, parametros: dict) -> dict:
    """El navegador se abre fuera del escritorio visible y solo se cierra su propio PID."""
    if not es_plataforma_compatible():
        raise RuntimeError("Win32 no esta disponible en esta distribucion")
    import win32api
    import win32con
    import win32gui

    margen = parametros["margen_fuera_pantalla"]
    ventana = ConfiguracionVentanaWeb(
        x=win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN) - parametros["ancho"] * margen,
        y=win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN) - parametros["alto"] * margen,
        ancho=parametros["ancho"], alto=parametros["alto"], siempre_al_frente=True,
    )
    configuracion = ConfiguracionWeb(directorio_base=raiz, nombre_perfil=parametros["perfil"], ventana=ventana)
    gestor = GestorSesionNodriver(configuracion)
    try:
        await gestor.abrir_nueva_pestana(parametros["url"], patrones_ventana=())
        hwnd = buscar_manejador_ventana((), gestor._pid_navegador, configuracion.directorio_perfil)
        if not hwnd:
            raise RuntimeError("No se encontro la ventana propia de comprobacion")
        izquierda, arriba, derecha, abajo = win32gui.GetWindowRect(hwnd)
        estilo = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        tamano = (derecha - izquierda, abajo - arriba)
        al_frente = bool(estilo & win32con.WS_EX_TOPMOST)
        if tamano != (ventana.ancho, ventana.alto) or not al_frente:
            raise RuntimeError(f"La politica de ventana no coincide: {tamano}, al_frente={al_frente}")
        return {"ancho": tamano[0], "alto": tamano[1], "al_frente": al_frente, "perfil_temporal": True}
    finally:
        if gestor._pid_navegador is None:
            hwnd = buscar_manejador_ventana((), directorio_perfil=configuracion.directorio_perfil)
            if hwnd:
                import win32process
                _, gestor._pid_navegador = win32process.GetWindowThreadProcessId(hwnd)
                gestor.forzar_cierre_inmediato()
        await gestor.cerrar_navegador()
