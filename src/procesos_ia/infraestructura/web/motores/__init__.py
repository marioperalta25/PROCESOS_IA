"""Subpaquete para manipuladores DOM de motores web dedicados (Gemini, DeepSeek)."""

from procesos_ia.infraestructura.web.motores.manipulador_dom_deepseek import (
    enviar_prompt_deepseek,
    esperar_respuesta_deepseek,
)
from procesos_ia.infraestructura.web.motores.manipulador_dom_gemini import (
    enviar_prompt_gemini,
    esperar_respuesta_gemini,
)

__all__ = [
    "enviar_prompt_deepseek",
    "enviar_prompt_gemini",
    "esperar_respuesta_deepseek",
    "esperar_respuesta_gemini",
]
