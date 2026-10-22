"""Modelos y tipos de datos para la integracion con Ollama y gestion de memoria."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class EstadoServicioOllama(str, Enum):
    """Estado de disponibilidad del servicio y ejecutable de Ollama."""

    DISPONIBLE = "disponible"
    DETENIDO = "detenido"
    NO_INSTALADO = "no_instalado"
    ERROR_CONEXION = "error_conexion"


@dataclass(frozen=True, slots=True)
class DiagnosticoOllama:
    """Resultado del diagnostico puntual del entorno local de Ollama."""

    estado: EstadoServicioOllama
    version_cliente: str | None
    version_servidor: str | None
    ruta_ejecutable: Path | None
    url_base: str
    mensaje: str


@dataclass(frozen=True, slots=True)
class InformacionModelo:
    """Metadatos de un modelo instalado localmente en Ollama."""

    nombre: str
    tamano_bytes: int
    familia: str
    formato: str
    parametros: str
    cuantizacion: str
    modificado_utc: str

    @property
    def tamano_gb(self) -> float:
        return round(self.tamano_bytes / (1024**3), 2)


@dataclass(frozen=True, slots=True)
class OpcionesInferencia:
    """Parametros de ejecucion e hiperparametros para la inferencia local."""

    temperatura: float = 0.1
    num_ctx: int = 2048
    keep_alive: str = "5m"
    top_p: float = 0.9
    seed: int | None = None
    tiempo_limite_segundos: float = 60.0
