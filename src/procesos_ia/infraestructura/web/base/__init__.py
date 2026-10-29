"""Subpaquete base para la sesion y utilidades de Chromium compartido."""

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

__all__ = [
    "ConfiguracionVentanaWeb",
    "ConfiguracionWeb",
    "GestorSesionNodriver",
    "ServicioInferenciaWeb",
    "aplicar_modo_flotante_sin_foco",
    "buscar_manejador_ventana",
    "es_plataforma_compatible",
    "extraer_y_reparar_json",
]
