"""Carga puntual de instrucciones y textos declarativos de evaluacion."""

from pathlib import Path
import tomllib

from procesos_ia.aplicacion.comun.localizador_recursos import obtener_ruta_recurso


def cargar_parametros_evaluacion(ruta: Path | None = None) -> dict:
    archivo = ruta or obtener_ruta_recurso("configuracion", "evaluaciones.toml")
    return tomllib.loads(archivo.read_text(encoding="utf-8"))
