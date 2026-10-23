"""Utilidad desacoplada para extraccion y reparacion de respuestas JSON en inferencia web."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def extraer_y_reparar_json(texto_crudo: str) -> dict[str, Any] | list[Any] | None:
    """Extrae y repara objetos o listas JSON contenidos en markdown o texto libre.

    No depende de ningun DOM especifico (DeepSeek, Gemini u otros).
    """
    if not texto_crudo or not texto_crudo.strip():
        return None

    # 1. Intentar capturar bloque markdown de codigo json ({...} o [...])
    coincidencia = re.search(r"```(?:json)?\s*([\{\[].*?[\}\]])\s*```", texto_crudo, re.DOTALL)
    if coincidencia:
        bloque = coincidencia.group(1).strip()
    else:
        # 2. Intentar capturar primer y ultimo delimitador json
        coincidencia_bloque = re.search(r"([\{\[].*[\}\]])", texto_crudo, re.DOTALL)
        bloque = coincidencia_bloque.group(1).strip() if coincidencia_bloque else texto_crudo.strip()

    # 3. Intentar parseo directo
    try:
        resultado = json.loads(bloque)
        if isinstance(resultado, (dict, list)):
            return resultado
    except Exception:
        pass

    # 4. Intentar reparacion de saltos de linea y caracteres de control
    bloque_limpio = bloque
    try:
        bloque_limpio = bloque.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
        resultado = json.loads(bloque_limpio)
        if isinstance(resultado, (dict, list)):
            return resultado
    except Exception:
        pass

    # 5. Intentar reparar comas finales redundantes (e.g. {"a": 1, } o [1, 2, ])
    try:
        bloque_sin_comas = re.sub(r",\s*([\}\]])", r"\1", bloque_limpio)
        resultado = json.loads(bloque_sin_comas)
        if isinstance(resultado, (dict, list)):
            return resultado
    except Exception:
        pass

    return None
