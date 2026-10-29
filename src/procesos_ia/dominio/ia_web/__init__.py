"""Subpaquete de dominio para entidades y logica de negocio de IA Web."""

from procesos_ia.dominio.ia_web.desglosador_telefonos import (
    desglosar_archivo_csv_telefonos,
    desglosar_ficha_por_telefono,
    desglosar_fichas_por_telefono,
    desglosar_fila_por_telefono,
    desglosar_filas_por_telefono,
    separar_telefonos,
)
from procesos_ia.dominio.ia_web.extractor_semantico_lens import (
    clasificar_etiqueta_semantica,
    extraer_datos_semanticos_lineas,
)
from procesos_ia.dominio.ia_web.ficha_negocio import FichaNegocioLens
from procesos_ia.dominio.ia_web.parseador_ficha_lens import parsear_sintesis_negocio

__all__ = [
    "FichaNegocioLens",
    "clasificar_etiqueta_semantica",
    "desglosar_archivo_csv_telefonos",
    "desglosar_ficha_por_telefono",
    "desglosar_fichas_por_telefono",
    "desglosar_fila_por_telefono",
    "desglosar_filas_por_telefono",
    "extraer_datos_semanticos_lineas",
    "parsear_sintesis_negocio",
    "separar_telefonos",
]
