"""Eleccion de continuacion local sin trasladar decisiones al escritor compartido."""

from PySide6.QtWidgets import QWidget

from procesos_ia.aplicacion.reanudacion_local import ContinuacionLocal
from procesos_ia.dominio.reanudacion import AccionReanudacion, ResumenReanudacion
from procesos_ia.interfaz.comun.dialogo_reanudacion import solicitar_decision_reanudacion


def elegir_continuacion_local(parent: QWidget, continuacion: ContinuacionLocal) -> str:
    """Presenta el dialogo unificado de reanudacion para el flujo de IA Local."""
    ruta_respaldo = continuacion.directorio / continuacion.nombre_archivo
    resumen = ResumenReanudacion(
        total=continuacion.confirmados,
        exitosos=continuacion.confirmados,
        fallidos=0,
        omitidos=0,
        pendientes=0,
        ruta_respaldo=ruta_respaldo,
        requiere_decision=True,
    )
    accion = solicitar_decision_reanudacion(resumen, parent=parent)
    if accion in (AccionReanudacion.CONTINUAR, AccionReanudacion.REPROCESAR_PENDIENTES):
        return "continuar"
    if accion == AccionReanudacion.REINICIAR_TODO:
        return "nuevo"
    return "cancelar"
