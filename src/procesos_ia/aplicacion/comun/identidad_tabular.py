"""Identidad y localizacion persistente de un trabajo tabular, sin guardar prompts."""

from dataclasses import dataclass
from functools import cache
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any
from types import MappingProxyType

from procesos_ia.aplicacion.salidas_proceso import cargar_configuracion_salidas


@cache
def parametros_tabulares() -> MappingProxyType:
    """Lee nombres persistidos y mensajes desde el recurso declarativo existente."""
    return MappingProxyType(cargar_configuracion_salidas()["tabular"])


def marca_archivo(ruta: Path) -> tuple[int, int]:
    estado = ruta.stat()
    return estado.st_size, estado.st_mtime_ns


@dataclass(frozen=True)
class IdentidadTabular:
    huella: str
    modulo: str
    origen: Path | None
    marca: tuple[int, int] | None
    total: int

    @classmethod
    def crear(
        cls, origen: Path | None, modulo: str, filas: list[dict[str, Any]],
        instrucciones: str, columnas: list[str] | None, opciones: dict | None = None,
    ) -> "IdentidadTabular":
        ruta = origen.resolve() if origen else None
        contrato = {
            "origen": os.path.normcase(str(ruta)) if ruta else None,
            "modulo": modulo, "filas": filas, "instrucciones": instrucciones.strip(),
            "columnas": columnas, "opciones": opciones or {},
        }
        contenido = json.dumps(contrato, sort_keys=True, ensure_ascii=False, default=str)
        huella = hashlib.sha256(contenido.encode("utf-8")).hexdigest()
        return cls(huella, modulo, ruta, marca_archivo(ruta) if ruta else None, len(filas))

    def verificar_origen(self, parametros: dict) -> None:
        if self.origen and (not self.origen.is_file() or marca_archivo(self.origen) != self.marca):
            raise ValueError(parametros["error_cambio"])


def leer_identidad(ruta: Path, parametros: dict) -> dict:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if not isinstance(datos, dict) or datos.get("version") != parametros["version"]:
            raise ValueError(parametros["error_identidad"])
        for clave in ("archivo_progreso", "archivo_salida"):
            nombre = datos[clave]
            if not isinstance(nombre, str) or Path(nombre).name != nombre or nombre in (".", ".."):
                raise ValueError(parametros["error_identidad"])
        return datos
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError(parametros["error_lectura"]) from error


def guardar_identidad(directorio: Path, identidad: IdentidadTabular, salida: str, parametros: dict) -> None:
    dir_estado = directorio / parametros.get("carpeta_estado", ".estado")
    dir_estado.mkdir(parents=True, exist_ok=True)
    ruta = dir_estado / parametros["archivo_identidad"]
    if ruta.exists():
        if leer_identidad(ruta, parametros).get("huella") != identidad.huella:
            raise ValueError(parametros["error_identidad"])
        return
    datos = {
        "version": parametros["version"], "huella": identidad.huella,
        "origen": str(identidad.origen) if identidad.origen else None,
        "modulo": identidad.modulo, "total": identidad.total, "creado_ns": time.time_ns(),
        "archivo_salida": salida, "archivo_progreso": parametros["archivo_progreso"],
    }
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=dir_estado, delete=False) as archivo:
            temporal = Path(archivo.name)
            json.dump(datos, archivo, ensure_ascii=False)
            archivo.flush()
            os.fsync(archivo.fileno())
        temporal.replace(ruta)
    finally:
        if temporal is not None:
            temporal.unlink(missing_ok=True)


def buscar_identidad(gestor: Any, identidad: IdentidadTabular, parametros: dict) -> Path | None:
    """Busca solo metadatos de la rama solicitada; acompanan a la carpeta al moverla."""
    candidatas = []
    carpeta_estado = parametros.get("carpeta_estado", ".estado")
    patrones = (f"*/{carpeta_estado}/{parametros['archivo_identidad']}", f"*/{parametros['archivo_identidad']}")
    for estado in gestor.configuracion["estados"].values():
        carpeta = gestor.rama(identidad.modulo) / estado
        for patron in patrones:
            for ruta in carpeta.glob(patron):
                datos = leer_identidad(ruta, parametros)
                if datos.get("huella") == identidad.huella:
                    candidatas.append((datos["creado_ns"], ruta, datos))
    if not candidatas:
        return None
    _, ruta, datos = max(candidatas, key=lambda item: item[0])
    progreso = ruta.parent / datos["archivo_progreso"]
    if not progreso.is_file():
        raise FileNotFoundError(parametros["error_respaldo"])
    return progreso
