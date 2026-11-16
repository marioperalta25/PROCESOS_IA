"""Localizador dinámico de recursos para entorno de desarrollo y empaquetado."""

from __future__ import annotations

import sys
from pathlib import Path


def obtener_ruta_recurso(*segmentos: str) -> Path:
    """Resuelve la ruta absoluta hacia un archivo o carpeta dentro de 'recursos'.

    Compatible con:
    1. Aplicacion empaquetada con PyInstaller (onedir y onefile via sys._MEIPASS o ejecutable).
    2. Entorno de desarrollo local de Python.
    """
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            meipass = Path(sys._MEIPASS) / "recursos" / Path(*segmentos)
            if meipass.exists():
                return meipass

        base_exe = Path(sys.executable).parent
        candidato_exe = base_exe / "recursos" / Path(*segmentos)
        if candidato_exe.exists():
            return candidato_exe

        candidato_internal = base_exe / "_internal" / "recursos" / Path(*segmentos)
        if candidato_internal.exists():
            return candidato_internal

    actual = Path(__file__).resolve()
    for ancestro in actual.parents:
        candidato = ancestro / "recursos" / Path(*segmentos)
        if candidato.exists():
            return candidato

    return Path.cwd() / "recursos" / Path(*segmentos)
