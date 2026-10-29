"""Paquete de infraestructura web para interacciones con Chromium y motores de IA."""

from procesos_ia.infraestructura.web.base.configuracion_web import (
    ConfiguracionVentanaWeb,
    ConfiguracionWeb,
)
from procesos_ia.infraestructura.web.base.controlador_ventana import (
    aplicar_modo_flotante_sin_foco,
    buscar_manejador_ventana,
    es_plataforma_compatible,
)
from procesos_ia.infraestructura.web.base.extractor_json import (
    extraer_y_reparar_json,
)
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.infraestructura.web.base.servicio_inferencia_web import ServicioInferenciaWeb
from procesos_ia.infraestructura.web.conversacional.manipulador_dom_modo_ia import (
    activar_modo_ia,
    enviar_prompt_modo_ia,
    esperar_respuesta_modo_ia,
    extraer_datos_estructurados_modo_ia,
)
from procesos_ia.infraestructura.web.motores.manipulador_dom_deepseek import (
    enviar_prompt_deepseek,
    esperar_respuesta_deepseek,
)
from procesos_ia.infraestructura.web.motores.manipulador_dom_gemini import (
    enviar_prompt_gemini,
    esperar_respuesta_gemini,
)
from procesos_ia.infraestructura.web.visual_1a1.manipulador_dom_lens import (
    abrir_modal_lens,
    cargar_archivo_en_lens,
    cargar_url_en_lens,
    esperar_vision_general_ia,
    extraer_enlaces_relacionados,
    parsear_sintesis_negocio,
)
from procesos_ia.infraestructura.web.visual_1a1.selectores_lens import (
    SELECTORES_LENS,
)

__all__ = [
    "ConfiguracionVentanaWeb",
    "ConfiguracionWeb",
    "GestorSesionNodriver",
    "SELECTORES_LENS",
    "ServicioInferenciaWeb",
    "abrir_modal_lens",
    "activar_modo_ia",
    "aplicar_modo_flotante_sin_foco",
    "buscar_manejador_ventana",
    "cargar_archivo_en_lens",
    "cargar_url_en_lens",
    "enviar_prompt_deepseek",
    "enviar_prompt_gemini",
    "enviar_prompt_modo_ia",
    "es_plataforma_compatible",
    "esperar_respuesta_deepseek",
    "esperar_respuesta_gemini",
    "esperar_respuesta_modo_ia",
    "esperar_vision_general_ia",
    "extraer_datos_estructurados_modo_ia",
    "extraer_enlaces_relacionados",
    "extraer_y_reparar_json",
    "parsear_sintesis_negocio",
]
