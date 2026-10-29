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
from procesos_ia.dominio.ia_web.desglosador_telefonos import (
    desglosar_archivo_csv_telefonos,
    desglosar_ficha_por_telefono,
    desglosar_fichas_por_telefono,
    desglosar_fila_por_telefono,
    desglosar_filas_por_telefono,
    separar_telefonos,
)
from procesos_ia.dominio.ia_web.ficha_negocio import FichaNegocioLens
from procesos_ia.dominio.ia_web.parseador_ficha_lens import parsear_sintesis_negocio
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
    "FichaNegocioLens",
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
    "desglosar_archivo_csv_telefonos",
    "desglosar_ficha_por_telefono",
    "desglosar_fichas_por_telefono",
    "desglosar_fila_por_telefono",
    "desglosar_filas_por_telefono",
    "formatear_columnas_delimitadas",
    "limpiar_espacios",
    "normalizar_clave_comparacion",
    "normalizar_datos_modelo",
    "normalizar_texto",
    "parsear_sintesis_negocio",
    "quitar_acentos",
    "reemplazar_enies",
    "separar_telefonos",
]

