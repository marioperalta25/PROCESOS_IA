"""Utilidades de detección de codificación, delimitadores y encabezados."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class InspeccionEncabezados:
    """Resultado del analisis estructural de las primeras filas del archivo."""

    tiene_encabezado: bool
    indice_fila_encabezado: int
    encabezados: list[str]
    filas_muestra: list[list[str]]


def detectar_codificacion(
    ruta_archivo: Path,
    candidatas: tuple[str, ...] = ("utf-8-sig", "utf-8", "latin-1", "cp1252"),
    bytes_muestreo: int = 65536,
) -> str:
    """Determina la codificacion que decodifica limpiamente los primeros bytes."""
    with open(ruta_archivo, "rb") as archivo:
        muestra = archivo.read(bytes_muestreo)

    for codificacion in candidatas:
        try:
            muestra.decode(codificacion)
            return codificacion
        except (UnicodeDecodeError, LookupError):
            continue

    return "latin-1"


def detectar_delimitador(
    ruta_archivo: Path,
    codificacion: str,
    delimitadores_candidatos: tuple[str, ...] = (",", ";", "\t", "|"),
    tamano_muestra: int = 32768,
) -> str:
    """Identifica el delimitador tabular con Sniffer o frecuencia relativa."""
    with open(ruta_archivo, "r", encoding=codificacion, errors="replace") as archivo:
        muestra = archivo.read(tamano_muestra)

    if not muestra.strip():
        return delimitadores_candidatos[0]

    try:
        dialecto = csv.Sniffer().sniff(
            muestra, delimiters="".join(delimitadores_candidatos)
        )
        return str(dialecto.delimiter)
    except csv.Error:
        # Conteo heuristico en lineas no vacias
        lineas = [lin for lin in muestra.splitlines() if lin.strip()][:5]
        conteo_max = -1
        mejor_delimitador = delimitadores_candidatos[0]
        for delim in delimitadores_candidatos:
            total_en_lineas = sum(linea.count(delim) for linea in lineas)
            if total_en_lineas > conteo_max:
                conteo_max = total_en_lineas
                mejor_delimitador = delim
        return mejor_delimitador


def detectar_encabezados(
    filas_iniciales: list[list[str]],
    max_filas_inspeccion: int = 5,
) -> InspeccionEncabezados:
    """Inspecciona hasta 5 filas iniciales para detectar encabezados y saltar vacias."""
    limite = min(len(filas_iniciales), max_filas_inspeccion)
    primer_indice_no_vacio = -1

    for i in range(limite):
        fila = [c.strip() for c in filas_iniciales[i] if c.strip()]
        if fila:
            primer_indice_no_vacio = i
            break

    if primer_indice_no_vacio == -1:
        return InspeccionEncabezados(
            tiene_encabezado=False,
            indice_fila_encabezado=0,
            encabezados=[],
            filas_muestra=[],
        )

    fila_candidata = [c.strip() for c in filas_iniciales[primer_indice_no_vacio]]
    tiene_encabezado = True

    # Si todos los elementos son numericos, no es encabezado
    son_numericos = sum(1 for c in fila_candidata if c.replace(".", "", 1).isdigit())
    if son_numericos == len(fila_candidata) and len(fila_candidata) > 0:
        tiene_encabezado = False

    # Si hay filas subsiguientes, comparar tipos
    if primer_indice_no_vacio + 1 < len(filas_iniciales):
        siguiente_fila = [
            c.strip() for c in filas_iniciales[primer_indice_no_vacio + 1]
        ]
        tipos_candidata = [c.isdigit() for c in fila_candidata]
        tipos_siguiente = [c.isdigit() for c in siguiente_fila]
        if tipos_candidata == tipos_siguiente and any(tipos_candidata):
            tiene_encabezado = False

    encabezados: list[str] = []
    if tiene_encabezado:
        for idx, col in enumerate(fila_candidata):
            nombre = col if col else f"columna_{idx + 1}"
            encabezados.append(nombre)
    else:
        encabezados = [f"columna_{idx + 1}" for idx in range(len(fila_candidata))]

    return InspeccionEncabezados(
        tiene_encabezado=tiene_encabezado,
        indice_fila_encabezado=primer_indice_no_vacio,
        encabezados=encabezados,
        filas_muestra=filas_iniciales[:limite],
    )
