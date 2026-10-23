"""Paquete de infraestructura para inferencia web mediante automatización de navegadores."""

from procesos_ia.infraestructura.web.configuracion_web import (
    ConfiguracionVentanaWeb,
    ConfiguracionWeb,
)
from procesos_ia.infraestructura.web.controlador_ventana import (
    aplicar_modo_flotante_sin_foco,
    buscar_manejador_ventana,
    es_plataforma_compatible,
)
from procesos_ia.infraestructura.web.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.infraestructura.web.servicio_inferencia_web import ServicioInferenciaWeb

__all__ = [
    "ConfiguracionVentanaWeb",
    "ConfiguracionWeb",
    "GestorSesionNodriver",
    "ServicioInferenciaWeb",
    "aplicar_modo_flotante_sin_foco",
    "buscar_manejador_ventana",
    "es_plataforma_compatible",
]
