"""Subpaquete para manipulacion DOM interactiva en Modo IA."""

from procesos_ia.infraestructura.web.conversacional.manipulador_dom_modo_ia import (
    activar_modo_ia,
    enviar_prompt_modo_ia,
    esperar_respuesta_modo_ia,
    extraer_datos_estructurados_modo_ia,
)

__all__ = [
    "activar_modo_ia",
    "enviar_prompt_modo_ia",
    "esperar_respuesta_modo_ia",
    "extraer_datos_estructurados_modo_ia",
]
