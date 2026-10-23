"""Persistencia ligera de la lista de modelos de Ollama para arranque instantaneo."""

from __future__ import annotations

import json
from pathlib import Path

from procesos_ia.infraestructura.ollama.modelos import InformacionModelo


class CacheModelosOllama:
    """Guarda y recupera en disco el ultimo listado de modelos conocidos."""

    def __init__(self, ruta_archivo: Path | None = None) -> None:
        if ruta_archivo is not None:
            self._ruta = ruta_archivo
        else:
            self._ruta = Path.home() / ".procesos_ia" / "cache_modelos.json"

    @property
    def ruta_archivo(self) -> Path:
        return self._ruta

    def cargar(self) -> list[InformacionModelo]:
        """Carga la lista de modelos desde cache si el archivo existe y es valido."""
        if not self._ruta.is_file():
            return []
        try:
            with open(self._ruta, "r", encoding="utf-8") as archivo:
                datos = json.load(archivo)
            if not isinstance(datos, list):
                return []
            modelos: list[InformacionModelo] = []
            for item in datos:
                if isinstance(item, dict) and item.get("nombre"):
                    modelos.append(
                        InformacionModelo(
                            nombre=str(item.get("nombre", "")),
                            tamano_bytes=int(item.get("tamano_bytes", 0)),
                            familia=str(item.get("familia", "")),
                            formato=str(item.get("formato", "")),
                            parametros=str(item.get("parametros", "")),
                            cuantizacion=str(item.get("cuantizacion", "")),
                            modificado_utc=str(item.get("modificado_utc", "")),
                        )
                    )
            return modelos
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return []

    def guardar(self, modelos: list[InformacionModelo]) -> bool:
        """Guarda la lista de modelos en cache asegurando la existencia del directorio."""
        try:
            self._ruta.parent.mkdir(parents=True, exist_ok=True)
            datos = [
                {
                    "nombre": m.nombre,
                    "tamano_bytes": m.tamano_bytes,
                    "familia": m.familia,
                    "formato": m.formato,
                    "parametros": m.parametros,
                    "cuantizacion": m.cuantizacion,
                    "modificado_utc": m.modificado_utc,
                }
                for m in modelos
            ]
            with open(self._ruta, "w", encoding="utf-8") as archivo:
                json.dump(datos, archivo, indent=2, ensure_ascii=False)
            return True
        except OSError:
            return False
