"""Parametros compartidos por el arranque manual, automatizado y sus comprobaciones."""

from functools import cache
import tomllib
from types import MappingProxyType

from procesos_ia.aplicacion.comun.localizador_recursos import obtener_ruta_recurso
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb


@cache
def parametros_navegador() -> MappingProxyType:
    ruta = obtener_ruta_recurso("configuracion", "navegador.toml")
    return MappingProxyType(tomllib.loads(ruta.read_text(encoding="utf-8")))


def argumentos_navegador(configuracion: ConfiguracionWeb, manual: bool = False) -> list[str]:
    """Deriva la geometria de las preferencias, sin depender del directorio de ejecucion."""
    parametros = parametros_navegador()
    ventana = configuracion.ventana
    argumentos = list(parametros["argumentos_comunes"])
    argumentos.extend((
        f"--window-size={ventana.ancho},{ventana.alto}",
        f"--window-position={ventana.x},{ventana.y}",
    ))
    if manual:
        argumentos.extend(parametros["argumentos_manuales"])
    return argumentos
