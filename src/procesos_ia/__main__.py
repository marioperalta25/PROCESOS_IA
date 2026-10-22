"""Punto de ejecución de paquete para python -m procesos_ia."""

from __future__ import annotations

import sys
from procesos_ia.interfaz.app import ejecutar_interfaz

if __name__ == "__main__":
    sys.exit(ejecutar_interfaz())
