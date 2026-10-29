"""Subpaquete de aplicacion para flujos conversacionales de IA Web."""

from procesos_ia.aplicacion.ia_web.conversacional.formateador_lotes_chat import (
    construir_prompt_lote_chat,
)
from procesos_ia.aplicacion.ia_web.conversacional.procesador_modo_ia import (
    ProcesadorModoIA,
)

__all__ = ["ProcesadorModoIA", "construir_prompt_lote_chat"]
