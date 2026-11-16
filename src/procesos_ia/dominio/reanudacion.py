"""Modelos y contratos de dominio para la reanudacion y reproceso granular."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class EstadoIA(str, Enum):
    """Estados discretos que puede tomar un registro procesado por IA."""

    EXITOSO = "EXITOSO"
    FALLIDO = "FALLIDO"
    OMITIDO = "OMITIDO"
    PENDIENTE = "PENDIENTE"

    @classmethod
    def normalizar(cls, valor: str | None) -> EstadoIA:
        """Normaliza cadenas arbitrarias al enum EstadoIA correspondiente."""
        if not valor:
            return cls.PENDIENTE
        v = str(valor).strip().upper()
        if "EXITOS" in v or "OK" in v or "COMPLETAD" in v:
            return cls.EXITOSO
        if "OMITID" in v or "SKIP" in v or "VACIO" in v:
            return cls.OMITIDO
        if "ERROR" in v or "FAIL" in v or "FALL" in v or "TIMEOUT" in v:
            return cls.FALLIDO
        return cls.PENDIENTE


class AccionReanudacion(str, Enum):
    """Accion elegida por el usuario o resuelta por la politica del sistema."""

    REPROCESAR_PENDIENTES_Y_FALLIDOS = "reprocesar_pendientes_y_fallidos"
    SOLO_PENDIENTES = "solo_pendientes"
    REINICIAR_TODO = "reiniciar_todo"
    RECUPERAR_RESULTADOS = "recuperar_resultados"
    CANCELAR = "cancelar"


@dataclass(slots=True)
class RegistroEstado:
    """Metadatos de estado asociados a una fila o imagen individual."""

    id_registro: str
    estado: EstadoIA = EstadoIA.PENDIENTE
    motivo: str = ""
    fecha_procesamiento: str = ""
    datos_originales: dict[str, Any] = field(default_factory=dict)

    @property
    def es_reintentable(self) -> bool:
        """Indica si el registro debe volver a enviarse a la IA."""
        return self.estado in (EstadoIA.FALLIDO, EstadoIA.OMITIDO, EstadoIA.PENDIENTE)


@dataclass(slots=True)
class ResumenReanudacion:
    """Estadisticas y diagnostico del archivo o carpeta para la toma de decisiones."""

    origen: Path
    total: int = 0
    exitosos: int = 0
    fallidos: int = 0
    omitidos: int = 0
    pendientes: int = 0
    tiene_metadatos: bool = False
    ruta_respaldo: Path | None = None

    @property
    def total_reintentables(self) -> int:
        """Suma de registros fallidos y omitidos con oportunidad de recuperacion."""
        return self.fallidos + self.omitidos

    @property
    def requiere_decision(self) -> bool:
        """Indica si amerita consultar al usuario por haber avance previo significativo."""
        return self.ruta_respaldo is not None or (
            self.tiene_metadatos and (self.exitosos > 0 or self.total_reintentables > 0)
        )
