"""Validacion y preparacion de la seleccion original en Modo IA."""

from pathlib import Path
from typing import Any

from procesos_ia.aplicacion.comun.identidad_tabular import parametros_tabulares
from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.interfaz.comun.preparacion_tabular import preparar_trabajo_con_dialogo
from procesos_ia.interfaz.ia_web.conversacional.medidor_tokens import LIMITE_CARACTERES_MODO_IA


def resolver_modo_ia(
    panel: Any, enrutador: EnrutadorSalidas, raiz_destino: Path | None,
    banner: Any, parent: Any,
) -> tuple[str, dict] | None:
    mensajes = parametros_tabulares()
    parametros = panel.obtener_parametros()
    if not parametros:
        banner.mostrar_error(mensajes["error_archivo"])
        return None
    if not parametros.get("columnas"):
        banner.mostrar_error(mensajes["error_columnas"])
        return None
    if not parametros.get("filas"):
        banner.mostrar_error(mensajes["error_vacio"])
        return None
    instrucciones = parametros.get("instrucciones", "")
    if len(instrucciones) > LIMITE_CARACTERES_MODO_IA:
        banner.mostrar_error(mensajes["error_prompt"].format(cantidad=len(instrucciones), limite=LIMITE_CARACTERES_MODO_IA))
        return None
    ruta_original = panel.obtener_ruta_archivo()
    if ruta_original and ruta_original.is_file():
        trabajo = preparar_trabajo_con_dialogo(
            enrutador, ruta_original, "modo_ia", instrucciones, parametros["columnas"], parametros["filas"],
            {"hoja": parametros.get("nombre_hoja")}, raiz_destino, parent,
        )
        if trabajo is None:
            return None
        parametros["trabajo_tabular"] = trabajo
        parametros["filas"] = trabajo.filas_pendientes
    return "modo_ia_lote", parametros
