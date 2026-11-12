"""Vistas interactivas de IA Web."""

from procesos_ia.interfaz.ia_web.vistas.vista_deepseek import VistaDeepSeek
from procesos_ia.interfaz.ia_web.vistas.vista_gemini import VistaGemini
from procesos_ia.interfaz.ia_web.vistas.vista_ia_general import VistaIAGeneral
from procesos_ia.interfaz.ia_web.vistas.vista_motores import (
    VistaConfiguracionMotores,
)

__all__ = [
    "VistaConfiguracionMotores",
    "VistaDeepSeek",
    "VistaGemini",
    "VistaIAGeneral",
]
