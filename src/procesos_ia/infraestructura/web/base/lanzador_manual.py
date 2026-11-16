"""Lanzamiento interactivo con el mismo perfil y politica de ventana de la automatizacion."""

import subprocess
from pathlib import Path

from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.controlador_ventana import aplicar_ventana_con_reintentos
from procesos_ia.infraestructura.web.base.parametros_navegador import argumentos_navegador, parametros_navegador


def lanzar_navegador_manual(url: str, configuracion: ConfiguracionWeb) -> int | None:
    """Devuelve el PID lanzado; una politica no aplicada se comunica como error visible."""
    from nodriver.core.config import find_chrome_executable
    ejecutable = find_chrome_executable()
    if not ejecutable or not Path(ejecutable).is_file():
        return None
    argumentos = [
        str(ejecutable), f"--user-data-dir={configuracion.directorio_perfil}",
        *argumentos_navegador(configuracion, manual=True), url,
    ]
    proceso = subprocess.Popen(argumentos, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    parametros = parametros_navegador()
    aplicado = aplicar_ventana_con_reintentos(
        parametros["patrones_titulo"], configuracion.ventana, proceso.pid, configuracion.directorio_perfil,
    )
    if not aplicado:
        raise RuntimeError(parametros["mensajes"]["ventana_no_aplicada"])
    return proceso.pid
