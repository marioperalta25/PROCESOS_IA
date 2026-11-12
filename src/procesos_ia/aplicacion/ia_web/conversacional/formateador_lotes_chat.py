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


def describir_formato_columnas(columnas: list[str] | tuple[str, ...] | None) -> str:
    """Describe el formato de las columnas para incluirlo en las instrucciones."""
    if not columnas:
        return "Cada registro contiene los datos de la fila."
    if len(columnas) == 1:
        return f"Cada registro contiene directamente el valor de la columna '{columnas[0]}'."
    cols_txt = ", ".join(f"'{c}'" for c in columnas)
    return (
        f"Las columnas ({cols_txt}) estan delimitadas exclusivamente por ' | ' "
        "en formato 'Columna: Valor'."
    )


def construir_prompt_inicial_conversacion(
    instrucciones: str,
    columnas_seleccionadas: list[str] | None = None,
    tamano_lote: int | None = None,
) -> str:
    """Construye el mensaje de apertura con las instrucciones del sistema para la conversacion."""
    instrucciones_limpias = compactar_instrucciones_prompt(instrucciones)
    partes = ["PROTOCOLO DE INTERACCION POR LOTES:"]

    if tamano_lote and tamano_lote > 1:
        partes.append(
            f"Te enviare registros en lotes de {tamano_lote} filas sucesivas identificadas como [FILA <id>]: <DATOS>."
        )
    else:
        partes.append(
            "Te enviare a continuacion registros en lotes sucesivos identificados como [FILA <id>]: <DATOS>."
        )

    if columnas_seleccionadas is not None:
        partes.append(describir_formato_columnas(columnas_seleccionadas))

    partes.append(
        "Debes responder para cada fila en estricto orden secuencial respetando exactamente las etiquetas indicadas."
    )
    partes.append(
        "Por favor confirma unicamente que has comprendido las instrucciones para comenzar."
    )
    aviso_protocolo = "\n".join(partes)
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
    total_filas = len(lote_filas)
    desc_cols = describir_formato_columnas(columnas_seleccionadas)

    lineas_datos = ["DATOS A EVALUAR:"]
    if total_filas > 1:
        lineas_datos.append(
            f"- Se envían {total_filas} filas. Cada fila inicia con la etiqueta '[FILA <id>]:' y debe responderse en el mismo orden."
        )
    else:
        lineas_datos.append("- Se envía 1 fila con la etiqueta '[FILA <id>]:'.")
    lineas_datos.append(f"- {desc_cols}")
    bloque_header = "\n".join(lineas_datos)

    aviso_formato = (
        'FORMATO DE RESPUESTA REQUERIDO:\n'
        'Responde estrictamente en formato JSON válido estructurado por la clave "resultados". '
        'Cada elemento DEBE incluir el campo "id" correspondiente a su fila y los campos evaluados según las instrucciones:\n'
        f'{{"resultados": [{{"id": {indice_inicio}, ...campos_evaluados...}}]}}\n'
        'Asegura que cada registro tenga su objeto correspondiente correlacionado por "id".'
    )
    return (
        f"{instrucciones_limpias}\n\n"
        f"{bloque_header}\n\n"
        f"{bloque_datos}\n\n"
        f"{aviso_formato}"
    )
