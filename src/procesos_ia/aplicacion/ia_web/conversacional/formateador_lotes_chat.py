"""Constructor y formateador de prompts y lotes tabulares con delimitador pipe."""

from __future__ import annotations

from typing import Any

from procesos_ia.dominio.normalizador import formatear_columnas_delimitadas


def construir_prompt_lote_chat(
    instrucciones: str,
    lote_filas: list[dict[str, Any]],
    columnas_seleccionadas: list[str] | None = None,
    indice_inicio: int = 1,
) -> str:
    """Construye un prompt enriquecido con filas delimitadas por pipe y contrato JSON."""
    lineas_datos: list[str] = []
    for sub_idx, fila in enumerate(lote_filas, start=0):
        id_fila = indice_inicio + sub_idx
        contenido_fila = formatear_columnas_delimitadas(fila, columnas_seleccionadas)
        lineas_datos.append(f"[FILA {id_fila}]: {contenido_fila}")

    bloque_datos = "\n".join(lineas_datos)
    instrucciones_limpias = instrucciones.strip() or "Evalúa los registros según su información."

    return (
        f"{instrucciones_limpias}\n\n"
        "DATOS A EVALUAR:\n"
        "- Cada FILA inicia con '[FILA <id>]:' y columnas separadas por ' | '.\n\n"
        f"{bloque_datos}\n\n"
        'Responde estrictamente en formato JSON válido con el siguiente esquema:\n'
        '{"resultados": [{"id": 1, "evaluacion": "..."}]}'
    )
