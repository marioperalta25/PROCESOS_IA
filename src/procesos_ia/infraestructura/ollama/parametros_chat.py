"""Parámetros declarativos compartidos por la conversación local."""

from pathlib import Path
import tomllib


def cargar_parametros_chat(ruta: Path | None = None) -> dict:
    archivo = ruta or (Path(__file__).resolve().parents[4]
                       / "recursos" / "configuracion" / "chat.toml")
    return tomllib.loads(archivo.read_text(encoding="utf-8"))
