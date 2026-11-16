"""Punto de ejecución de paquete para python -m procesos_ia."""

from __future__ import annotations

import sys
from pathlib import Path


def principal() -> int:
    from multiprocessing import freeze_support
    freeze_support()
    from procesos_ia.infraestructura.web.base.parametros_navegador import parametros_navegador
    bandera = parametros_navegador()["comprobacion"]["argumento"]
    if len(sys.argv) == 3 and sys.argv[1] == bandera:
        from procesos_ia.aplicacion.inicio.comprobacion_distribucion import ejecutar_comprobacion
        return ejecutar_comprobacion(Path(sys.argv[2]))
    from procesos_ia.interfaz.app import ejecutar_interfaz
    return ejecutar_interfaz()

if __name__ == "__main__":
    sys.exit(principal())
