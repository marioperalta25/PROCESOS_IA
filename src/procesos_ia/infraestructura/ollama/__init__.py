"""Adaptadores de infraestructura para comunicación con el motor local de Ollama."""

from __future__ import annotations

from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.ollama.modelos import (
    DiagnosticoOllama,
    EstadoServicioOllama,
    InformacionModelo,
    OpcionesInferencia,
)
from procesos_ia.infraestructura.ollama.servicio_inferencia import (
    ServicioInferenciaOllama,
)

__all__ = [
    "ClienteHttpOllama",
    "DiagnosticoOllama",
    "EstadoServicioOllama",
    "InformacionModelo",
    "OpcionesInferencia",
    "ServicioInferenciaOllama",
]
