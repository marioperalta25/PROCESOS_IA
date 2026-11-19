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
    r"^(?:aqu[ií]\s+tienes|aqu[ií]\s+est[aá]|espero\s+que\s+esto|tienes\s+un\s+nuevo)",
    r"^(?:claro|por\s+supuesto|entendido)[\.,:\s]*$",
    r"^(?:resultados?|lista|salida|respuesta)\s*:\s*$",
    r"^(?:sure|here\s+are|ready\s+for|please\s+send)",
    r"\?\s*$",
)


def verificar_conexion_internet(host: str = "8.8.8.8", port: int = 53, timeout: float = 3.0) -> bool:
    """Comprueba salida a internet por socket directo, HTTPS 443 o proxy HTTP del sistema."""
    destinos = [(host, port)]
    if (host, port) == ("8.8.8.8", 53):
        destinos.extend((("www.google.com", 443), ("1.1.1.1", 443)))
    for h, p in destinos:
        try:
            with socket.create_connection((h, p), timeout=timeout):
                return True
        except OSError:
            continue
    if (host, port) == ("8.8.8.8", 53):
        try:
            import urllib.request
            with urllib.request.urlopen("https://www.google.com/generate_204", timeout=timeout) as resp:
                return int(getattr(resp, "status", 200)) < 500
        except Exception:
            pass
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

    inicio = asyncio.get_running_loop().time()
    while (asyncio.get_running_loop().time() - inicio) < timeout_max_seg:
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
    """Determina si una linea de texto corresponde a cortesia, encabezado o metatexto del modelo."""
    lin = linea.strip()
    if not lin:
        return True
    if lin.startswith("#") or re.fullmatch(r"[-*_]{3,}", lin):
        return True
    if lin.endswith(":") and "|" not in lin:
        return True
    if re.search(r"\b(?:a\s+continuaci[oó]n|below\s+are|these\s+are)\b", lin, re.IGNORECASE):
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


PATRONES_CAPTCHA_GOOGLE = (
    r"nuestros sistemas han detectado tr[aá]fico inusual",
    r"unusual traffic from your computer network",
    r"detected unusual traffic",
    r"id=[\"']captcha-form[\"']",
    r"class=[\"'][^\"']*g-recaptcha",
    r"recaptcha/enterprise\.js",
)


def es_texto_captcha_google(url: str = "", html_o_texto: str = "") -> bool:
    """Indica si la URL o contenido corresponde a la pantalla CAPTCHA (/sorry/) de Google."""
    url_low = (url or "").lower()
    if "/sorry/" in url_low or "sorry/index" in url_low:
        return True
    contenido = html_o_texto or ""
    if not contenido:
        return False
    return any(re.search(pat, contenido, re.IGNORECASE) for pat in PATRONES_CAPTCHA_GOOGLE)


async def detectar_captcha_pestana(pestana: Any) -> bool:
    """Inspecciona URL y DOM de la pestana activa para detectar bloqueo CAPTCHA de Google."""
    if pestana is None:
        return False
    url_attr = str(getattr(pestana, "url", "") or "")
    if es_texto_captcha_google(url=url_attr):
        return True
    js = """(() => JSON.stringify({
        url: location.href || "",
        captcha: Boolean(document.querySelector("#captcha-form, form[action*='sorry'], #recaptcha, .g-recaptcha, iframe[src*='recaptcha']")),
        texto: (document.body && document.body.innerText ? document.body.innerText.slice(0, 1200) : "")
    }))()"""
    try:
        import json
        res = await asyncio.wait_for(pestana.evaluate(js), timeout=2.0)
        if isinstance(res, str) and res.startswith("{"):
            datos = json.loads(res)
            if bool(datos.get("captcha")):
                return True
            return es_texto_captcha_google(str(datos.get("url", "")), str(datos.get("texto", "")))
    except Exception:
        pass
    return False


async def recuperar_si_captcha_google(
    pestana: Any,
    gestor_sesion: Any,
    callback_log: Any = None,
    espera_segundos: float = 2.0,
) -> bool:
    """Si hay CAPTCHA en pestana: cierra navegador, purga y recrea perfil, y espera."""
    if not await detectar_captcha_pestana(pestana):
        return False
    if callback_log:
        callback_log(
            f"[ALERTA] CAPTCHA de Google detectado. Cerrando navegador, esperando {espera_segundos:.0f}s y reiniciando con perfil limpio..."
        )
    logger.warning("[ALERTA] CAPTCHA de Google detectado. Ejecutando reinicio con perfil limpio.")
    purgado = await gestor_sesion.reiniciar_con_perfil_limpio()
    if purgado is False and callback_log:
        callback_log("[ALERTA] No se pudo eliminar por completo la carpeta del perfil (archivos retenidos por el sistema).")
    await asyncio.sleep(espera_segundos)
    return True

