"""Carga puntual de instrucciones y textos declarativos de evaluacion."""

from pathlib import Path
import tomllib


def cargar_parametros_evaluacion(ruta: Path | None = None) -> dict:
    archivo = ruta or (
        Path(__file__).resolve().parents[4]
        / "recursos" / "configuracion" / "evaluaciones.toml"
    )
    return tomllib.loads(archivo.read_text(encoding="utf-8"))
