"""Persistencia ligera de preferencias de ventana y sesion web mediante QSettings."""

from __future__ import annotations

from dataclasses import replace
from PySide6.QtCore import QSettings

from procesos_ia.infraestructura.web.base.configuracion_web import (
    ConfiguracionVentanaWeb,
    ConfiguracionWeb,
)


def _obtener_settings(settings: QSettings | None = None) -> QSettings:
    return settings if settings is not None else QSettings("PROCESOS_IA", "PROCESOS_IA")


def cargar_configuracion_web(settings: QSettings | None = None) -> ConfiguracionWeb:
    """Recupera la geometria y opciones web guardadas por el usuario."""
    st = _obtener_settings(settings)
    base = ConfiguracionWeb()
    ventana_base = base.ventana
    ancho = max(200, int(st.value("web/ancho", ventana_base.ancho)))
    alto = max(200, int(st.value("web/alto", ventana_base.alto)))
    al_frente = str(st.value("web/siempre_al_frente", ventana_base.siempre_al_frente)).lower() in ("true", "1", "yes")
    espera = max(5, min(300, int(st.value("web/tiempo_espera", base.tiempo_espera_respuesta_segundos))))
    auditoria = str(st.value("web/generar_auditoria_md", base.generar_auditoria_md)).lower() in ("true", "1", "yes")
    ventana = replace(ventana_base, ancho=ancho, alto=alto, siempre_al_frente=al_frente)
    return replace(base, ventana=ventana, tiempo_espera_respuesta_segundos=espera, generar_auditoria_md=auditoria)


def guardar_configuracion_web(configuracion: ConfiguracionWeb, settings: QSettings | None = None) -> None:
    """Persiste la geometria y opciones web configuradas por el usuario."""
    st = _obtener_settings(settings)
    st.setValue("web/ancho", int(configuracion.ventana.ancho))
    st.setValue("web/alto", int(configuracion.ventana.alto))
    st.setValue("web/siempre_al_frente", bool(configuracion.ventana.siempre_al_frente))
    st.setValue("web/tiempo_espera", int(configuracion.tiempo_espera_respuesta_segundos))
    st.setValue("web/generar_auditoria_md", bool(configuracion.generar_auditoria_md))
    st.sync()
