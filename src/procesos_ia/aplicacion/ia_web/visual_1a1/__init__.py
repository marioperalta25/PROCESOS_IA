"""Subpaquete de aplicacion para procesamiento visual 1 a 1 de imagenes y URLs."""

from procesos_ia.aplicacion.ia_web.visual_1a1.procesador_archivo_urls import ProcesadorArchivoUrls
from procesos_ia.aplicacion.ia_web.visual_1a1.procesador_carpeta_imagenes import ProcesadorCarpetaImagenes
from procesos_ia.aplicacion.ia_web.visual_1a1.procesador_url_individual import ProcesadorUrlIndividual
from procesos_ia.aplicacion.ia_web.visual_1a1.servicio_ia_general import ServicioIAGeneral

__all__ = [
    "ProcesadorArchivoUrls",
    "ProcesadorCarpetaImagenes",
    "ProcesadorUrlIndividual",
    "ServicioIAGeneral",
]
