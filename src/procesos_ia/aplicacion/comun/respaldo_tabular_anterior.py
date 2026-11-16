"""Importacion conservadora de CSVs anteriores sin identidad persistida."""

from pathlib import Path
import re
from typing import Any

from procesos_ia.aplicacion.comun.gestor_reanudacion_base import COLUMNA_ID, identificar_fila
from procesos_ia.aplicacion.comun.trabajo_tabular import leer_progreso
from procesos_ia.aplicacion.ia_web.conversacional.formateador_lotes_chat import (
    compactar_instrucciones_prompt, construir_mensaje_lote_datos,
)
from procesos_ia.dominio.ia_web.desglosador_telefonos import desglosar_filas_por_telefono


def _leer_cabecera_auditoria(ruta: Path) -> str:
    """Lee solo instrucciones y primera entrada; evita cargar el HTML de todos los lotes."""
    lineas = []
    entrada = False
    bloque_abierto = False
    with ruta.open(encoding="utf-8") as archivo:
        for linea in archivo:
            lineas.append(linea)
            if linea.strip() == "**Entrada Enviada:**":
                entrada = True
            elif entrada and linea.startswith("```"):
                if bloque_abierto:
                    break
                bloque_abierto = True
    return "".join(lineas)


def importar_respaldo_anterior(
    ruta: Path, originales: list[dict[str, Any]], instrucciones: str,
    columnas: list[str] | None, parametros: dict,
) -> list[dict[str, Any]] | None:
    """Exige instrucciones, datos enviados e identidad de cada fila; no basta el nombre."""
    auditoria = ruta.with_suffix(".md")
    if not auditoria.is_file():
        return None
    texto = _leer_cabecera_auditoria(auditoria)
    prompt = re.search(r"## Prompt Inicial del Sistema\s+```text\n(.*?)\n```", texto, re.S)
    entrada = re.search(r"\*\*Entrada Enviada:\*\*\s+```text\n(.*?)\n```", texto, re.S)
    if not prompt or not entrada:
        return None
    if compactar_instrucciones_prompt(prompt[1]) != compactar_instrucciones_prompt(instrucciones):
        return None
    cantidad = len(entrada[1].splitlines())
    esperado = construir_mensaje_lote_datos(originales[:cantidad], columnas, 1)
    if entrada[1] != esperado:
        return None
    filas = leer_progreso(ruta, parametros)
    mapa = {identificar_fila(f, i): f for i, f in enumerate(originales, 1)}
    recuperadas = {}
    for fila in filas:
        identificador = str(fila.get(COLUMNA_ID, "")).strip()
        original = mapa.get(identificador)
        if original is None:
            return None
        # El exportador anterior normalizaba o desglosaba telefonos en las filas de salida.
        variantes = desglosar_filas_por_telefono([original])
        if not any(all(fila.get(k) == (str(v) if v is not None else "") for k, v in variante.items()) for variante in variantes):
            return None
        if identificador in recuperadas:
            return None
        recuperadas[identificador] = {**fila, **original, COLUMNA_ID: identificador}
    return list(recuperadas.values()) or None
