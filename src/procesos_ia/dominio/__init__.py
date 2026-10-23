"""Modulo de dominio para el procesamiento de datos con IA local."""

from __future__ import annotations

from procesos_ia.dominio.excepciones import (
    ErrorIntegridadWal,
    ErrorProcesamiento,
    ErrorRecuperacionProgreso,
    ErrorValidacionSemantica,
)
from procesos_ia.dominio.modelos import (
    ConfiguracionTrabajo,
    EstadoProcesamiento,
    IdentificadorRegistro,
    MetricasProgreso,
    RegistroConfirmado,
    RegistroEntrada,
    ResultadoEvaluacion,
    TransaccionWal,
)
from procesos_ia.dominio.normalizador import (
    formatear_columnas_delimitadas,
    limpiar_espacios,
    normalizar_clave_comparacion,
    normalizar_datos_modelo,
    normalizar_texto,
    quitar_acentos,
    reemplazar_enies,
)
from procesos_ia.dominio.prompts import (
    PeticionRefinamiento,
    PlantillaPrompt,
    ResultadoRefinamiento,
)
from procesos_ia.dominio.validador import ValidadorSemantico

__all__ = [
    "ConfiguracionTrabajo",
    "ErrorIntegridadWal",
    "ErrorProcesamiento",
    "ErrorRecuperacionProgreso",
    "ErrorValidacionSemantica",
    "EstadoProcesamiento",
    "IdentificadorRegistro",
    "MetricasProgreso",
    "PeticionRefinamiento",
    "PlantillaPrompt",
    "RegistroConfirmado",
    "RegistroEntrada",
    "ResultadoEvaluacion",
    "ResultadoRefinamiento",
    "TransaccionWal",
    "ValidadorSemantico",
    "formatear_columnas_delimitadas",
    "limpiar_espacios",
    "normalizar_clave_comparacion",
    "normalizar_datos_modelo",
    "normalizar_texto",
    "quitar_acentos",
    "reemplazar_enies",
]
