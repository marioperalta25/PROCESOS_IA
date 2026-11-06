"""Gestor global de resiliencia, clasificacion de fallos y salvaguarda para IA Web."""

from __future__ import annotations

import asyncio
from enum import Enum
import logging
from pathlib import Path
import re
import socket
from typing import Any

from procesos_ia.aplicacion.ia_web.comun.guardador_extracciones import (
    guardar_filas_enriquecidas_csv,
)

logger = logging.getLogger(__name__)


class TipoFalloWeb(str, Enum):
    """Categorizacion estandarizada de anomalias operativas en automatizacion web."""

    SIN_CONEXION = "sin_conexion"
    LIMITE_IA = "limite_ia"
    NAVEGADOR_CAIDO = "navegador_caido"
    LOTE_INCOMPLETO = "lote_incompleto"
    TIMEOUT_INFERENCIA = "timeout_inferencia"
    DESCONOCIDO = "desconocido"


PATRONES_LIMITE_IA = (
    r"alcanzaste el l[ií]mite de solicitudes",
    r"l[ií]mite de respuestas de ia",
    r"vuelve a intentarlo m[aá]s tarde",
    r"reached the limit of ai",
    r"too many requests",
)

PATRONES_CORTESIA_CONVERSACIONAL = (
    r"^(?:he\s+completado|procesamiento\s+completado|listo\s+para)",
    r"^(?:env[ií]a\s+el\s+siguiente|quedo\s+a\s+la\s+espera)",
    r"^(?:aqu[ií]\s+tienes|espero\s+que\s+esto|tienes\s+un\s+nuevo)",
    r"^(?:sure|here\s+are|ready\s+for|please\s+send)",
    r"\?\s*$",
)


def verificar_conexion_internet(host: str = "8.8.8.8", port: int = 53, timeout: float = 3.0) -> bool:
    """Comprueba disponibilidad real de salida a internet mediante socket ultraligero."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


async def esperar_restablecimiento_conexion(
    callback_log: Any = None,
    timeout_max_seg: float = 300.0,
    intervalo_seg: float = 4.0,
) -> bool:
    """Pausa reactivamente el flujo ante caida de red y reanuda cuando se restablece."""
    if verificar_conexion_internet():
        return True

    if callback_log:
        callback_log("[ALERTA] Sin conexion a internet detectada. Pausando proceso...")
    logger.warning("[ALERTA] Conexion perdida. Esperando recuperacion...")

    inicio = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - inicio) < timeout_max_seg:
        await asyncio.sleep(intervalo_seg)
        if verificar_conexion_internet():
            if callback_log:
                callback_log("[OK] Conexion a internet restablecida. Reanudando proceso...")
            logger.info("[OK] Conexion restablecida.")
            return True

    if callback_log:
        callback_log("[ERROR] Tiempo limite de espera de conexion agotado.")
    return False


def clasificar_fallo_web(
    excepcion: Exception | None = None,
    texto_resp: str = "",
) -> TipoFalloWeb:
    """Clasifica el tipo de incidente a partir de excepciones del runtime o texto del DOM."""
    if not verificar_conexion_internet():
        return TipoFalloWeb.SIN_CONEXION

    if texto_resp:
        for patron in PATRONES_LIMITE_IA:
            if re.search(patron, texto_resp, re.IGNORECASE):
                return TipoFalloWeb.LIMITE_IA

    if excepcion is not None:
        msj = str(excepcion).lower()
        if any(term in msj for term in ("disconnected", "connection refused", "target closed", "cdp", "process died")):
            return TipoFalloWeb.NAVEGADOR_CAIDO
        if any(term in msj for term in ("timeout", "timed out", "asyncio.exceptions.timeouterror")):
            return TipoFalloWeb.TIMEOUT_INFERENCIA

    return TipoFalloWeb.DESCONOCIDO


def es_linea_conversacional(linea: str) -> bool:
    """Determina si una linea de texto corresponde a cortesía o metatexto del modelo."""
    lin = linea.strip()
    if not lin:
        return True
    if len(lin) > 75 and any(palabra in lin.lower() for palabra in ("lote", "registro", "proces", "siguiente")):
        return True
    for patron in PATRONES_CORTESIA_CONVERSACIONAL:
        if re.search(patron, lin, re.IGNORECASE):
            return True
    return False


def filtrar_lineas_datos_ia(texto_resp: str, max_filas: int = 0) -> list[str]:
    """Extrae exclusivamente las lineas de datos utiles eliminando charla conversacional."""
    lineas_candidatas: list[str] = []
    for l in texto_resp.splitlines():
        lin = l.strip()
        if not lin or lin.startswith("```") or lin.startswith("Respuesta"):
            continue
        if es_linea_conversacional(lin):
            continue
        lineas_candidatas.append(lin)
    return lineas_candidatas[:max_filas] if max_filas > 0 else lineas_candidatas


def salvaguardar_progreso_csv(filas: list[dict[str, Any]], ruta_salida: Path) -> bool:
    """Guarda incrementalmente el estado de las filas en disco de forma segura."""
    if not filas or not ruta_salida:
        return False
    try:
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        guardar_filas_enriquecidas_csv(filas, ruta_salida)
        return True
    except Exception as err:
        logger.error("[ERROR] Fallo al salvaguardar CSV parcial: %s", err)
        return False

