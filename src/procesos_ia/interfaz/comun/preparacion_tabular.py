"""Decision de continuacion compartida por las vistas tabulares."""

from pathlib import Path
from typing import Any
from PySide6.QtWidgets import QMessageBox

from procesos_ia.aplicacion.comun.identidad_tabular import parametros_tabulares
from procesos_ia.aplicacion.comun.trabajo_tabular import TrabajoTabular
from procesos_ia.aplicacion.ia_web.comun.gestor_reanudacion_tabular import GestorReanudacionTabular
from procesos_ia.dominio.reanudacion import AccionReanudacion
from procesos_ia.interfaz.comun.dialogo_reanudacion import solicitar_decision_reanudacion


def preparar_trabajo_con_dialogo(
    enrutador: Any, ruta: Path, modulo: str, instrucciones: str,
    columnas: list[str] | None, filas: list[dict[str, Any]], opciones: dict | None = None,
    raiz_destino: Path | None = None, parent: Any = None,
) -> TrabajoTabular | None:
    """No mueve salidas ni inicia ejecuciones antes de resolver la decision del usuario."""
    parametros = parametros_tabulares()
    try:
        trabajo = GestorReanudacionTabular(enrutador, raiz_destino).preparar_trabajo(
            ruta, modulo, instrucciones, columnas, filas, opciones,
        )
        if trabajo.resumen.requiere_decision:
            accion = solicitar_decision_reanudacion(trabajo.resumen, parent=parent)
            if accion == AccionReanudacion.CANCELAR:
                return None
            trabajo.seleccionar(accion)
        if not trabajo.filas_pendientes and not trabajo.solo_exportar:
            QMessageBox.information(parent, parametros["titulo_progreso"], parametros["sin_pendientes"])
            return None
        return trabajo
    except (OSError, ValueError, RuntimeError) as error:
        QMessageBox.warning(parent, parametros["titulo_progreso"], str(error))
        return None
