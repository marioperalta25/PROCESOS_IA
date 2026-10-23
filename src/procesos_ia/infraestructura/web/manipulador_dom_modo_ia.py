"""Manipulador DOM para Modo IA de Google Search (SGE / Gemini en Buscador)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from procesos_ia.infraestructura.web.extractor_json import extraer_y_reparar_json

logger = logging.getLogger(__name__)


async def activar_modo_ia(pestana: Any) -> bool:
    """Activa el Modo IA haciendo clic en el boton correspondiente."""
    selectores = [
        "button.plR5qb",
        "button[jsname='B6rgad']",
        "span.lTxWLe",
        "#composeButton",
        "cr-button#composeButton",
        "cr-button[aria-label*='Modo IA']",
        "cr-button.compose-container",
    ]
    for sel in selectores:
        try:
            elem = await pestana.select(sel, timeout=2)
            if elem is not None:
                await elem.click()
                await asyncio.sleep(1.0)
                return True
        except Exception:
            continue
    return False


async def enviar_prompt_modo_ia(pestana: Any, prompt: str) -> bool:
    """Introduce las instrucciones en el textarea de Modo IA o busqueda y envia la peticion."""
    selectores_input = [
        "textarea.gLFyf",
        "textarea#ti6dpd",
        "textarea[name='q']",
        "textarea[jsname='yZiJbe']",
        "textarea#input",
        "#composeboxInput textarea",
        "#inputWrapper textarea",
        "textarea[part='input']",
    ]
    elem_input = None
    for sel in selectores_input:
        try:
            elem_input = await pestana.select(sel, timeout=2)
            if elem_input is not None:
                break
        except Exception:
            continue

    if elem_input is None:
        logger.warning("[ALERTA] No se encontro campo de entrada en Modo IA")
        return False

    try:
        await elem_input.send_keys(prompt)
        await asyncio.sleep(0.5)

        btn_submit = await pestana.select("cr-composebox-submit", timeout=1)
        if btn_submit is not None:
            await btn_submit.click()
        else:
            await elem_input.send_keys("\n")

        await asyncio.sleep(2.0)
        return True
    except Exception as error:
        logger.error("[ERROR] Fallo al enviar prompt a Modo IA: %s", error)
        return False


async def esperar_respuesta_modo_ia(
    pestana: Any, timeout_segundos: int = 45, estabilidad_segundos: float = 1.5
) -> str:
    """Espera a que termine de generarse la respuesta en Modo IA."""
    tiempo_inicio = asyncio.get_event_loop().time()
    ultimo_texto = ""
    ultimo_cambio = tiempo_inicio

    selectores_respuesta = [
        ".BpxUDf.aiModeUiCodeBlock__Container",
        ".n6owBd",
        ".mZJni.Dn7Fzd",
        ".EyBRub",
    ]

    while (asyncio.get_event_loop().time() - tiempo_inicio) < timeout_segundos:
        texto_actual = ""
        for sel in selectores_respuesta:
            try:
                elem = await pestana.select(sel, timeout=1)
                if elem is not None:
                    txt = getattr(elem, "text", "") or ""
                    if txt:
                        texto_actual = txt
                        break
            except Exception:
                continue

        if texto_actual:
            if texto_actual != ultimo_texto:
                ultimo_texto = texto_actual
                ultimo_cambio = asyncio.get_event_loop().time()
            elif (asyncio.get_event_loop().time() - ultimo_cambio) >= estabilidad_segundos:
                return ultimo_texto

        await asyncio.sleep(1.0)

    return ultimo_texto


def extraer_datos_estructurados_modo_ia(texto_respuesta: str) -> dict[str, Any] | list[Any]:
    """Extrae y repara bloques JSON generados por Modo IA."""
    return extraer_y_reparar_json(texto_respuesta)
