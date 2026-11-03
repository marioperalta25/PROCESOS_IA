"""Constructor y formateador de prompts y lotes tabulares con delimitador pipe."""

from __future__ import annotations

import re
from typing import Any

from procesos_ia.dominio.normalizador import formatear_columnas_delimitadas


def compactar_instrucciones_prompt(instrucciones: str) -> str:
    """Elimina separadores redundantes, saltos triples y espacios extra sin perder significado."""
    if not instrucciones:
        return ""
    texto = instrucciones.strip()
    texto = re.sub(r"[-=]{4,}", "---", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    lineas = [re.sub(r"[ \t]{2,}", " ", l).strip() for l in texto.splitlines()]
    return "\n".join(lineas).strip()


def construir_prompt_inicial_conversacion(instrucciones: str) -> str:
    """Construye el mensaje de apertura con las instrucciones del sistema para la conversacion."""
    instrucciones_limpias = compactar_instrucciones_prompt(instrucciones)
    aviso_protocolo = (
        "PROTOCOLO DE INTERACCION POR LOTES:\n"
        "Te enviare a continuacion registros en lotes sucesivos identificados como [FILA <id>]: <DATOS>.\n"
        "Debes responder para cada fila en estricto orden respetando exactamente las etiquetas indicadas.\n"
        "Por favor confirma unicamente que has comprendido las instrucciones para comenzar."
    )
    return f"{instrucciones_limpias}\n\n{aviso_protocolo}"


def construir_mensaje_lote_datos(
    lote_filas: list[dict[str, Any]],
    columnas_seleccionadas: list[str] | None = None,
    indice_inicio: int = 1,
) -> str:
    """Construye un mensaje ligero conteniendo exclusivamente las filas del lote."""
    lineas_datos: list[str] = []
    for sub_idx, fila in enumerate(lote_filas):
        id_fila = indice_inicio + sub_idx
        contenido_fila = formatear_columnas_delimitadas(fila, columnas_seleccionadas)
        lineas_datos.append(f"[FILA {id_fila}]: {contenido_fila}")
    return "\n".join(lineas_datos)


def construir_prompt_lote_chat(
    instrucciones: str,
    lote_filas: list[dict[str, Any]],
    columnas_seleccionadas: list[str] | None = None,
    indice_inicio: int = 1,
) -> str:
    """Construye un prompt combinado con instrucciones y filas para modo monolitico."""
    bloque_datos = construir_mensaje_lote_datos(lote_filas, columnas_seleccionadas, indice_inicio)
    instrucciones_limpias = compactar_instrucciones_prompt(instrucciones) or "Evalúa los registros según su información."
    aviso_formato = (
        'FORMATO DE RESPUESTA REQUERIDO:\n'
        'Responde estrictamente en formato JSON válido estructurado por la clave "resultados". '
        'Cada elemento DEBE incluir el campo "id" correspondiente a su fila y los campos evaluados según las instrucciones:\n'
        '{"resultados": [{"id": 1, ...campos_evaluados...}]}\n'
        'Asegura que cada registro tenga su objeto correspondiente correlacionado por "id".'
    )
    return (
        f"{instrucciones_limpias}\n\n"
        "DATOS A EVALUAR:\n"
        "- Cada FILA inicia con '[FILA <id>]:' y columnas separadas por ' | '.\n\n"
        f"{bloque_datos}\n\n"
        f"{aviso_formato}"
    )
