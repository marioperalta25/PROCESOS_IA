"""Modulo de dominio para el desglose y duplicacion de registros por multiples telefonos."""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from procesos_ia.dominio.ia_web.ficha_negocio import FichaNegocioLens

RE_TELEFONO_ESTRICTO = re.compile(
    r"(?:(?:\+?1|\b1)[-.\s]*)?\(?([2-9]\d{2})\)?[-.\s]*(\d{3})[-.\s]*(\d{4})\b"
)


def limpiar_numero_individual(telefono: str) -> str:
    """Extrae y normaliza un numero telefonico a exactamente 10 digitos formato (XXX) XXX-XXXX."""
    if not telefono:
        return ""
    m = RE_TELEFONO_ESTRICTO.search(telefono)
    if m:
        return f"({m.group(1)}) {m.group(2)}-{m.group(3)}"
    return ""


def separar_telefonos(cadena_telefonos: str | None) -> list[str]:
    """Separa y normaliza telefonos validos de exactamente 10 digitos en formato (XXX) XXX-XXXX."""
    if not cadena_telefonos:
        return []
    texto = str(cadena_telefonos).strip()
    if not texto:
        return []

    numeros_unicos: list[str] = []
    for m in RE_TELEFONO_ESTRICTO.finditer(texto):
        num_formateado = f"({m.group(1)}) {m.group(2)}-{m.group(3)}"
        if num_formateado not in numeros_unicos:
            numeros_unicos.append(num_formateado)
    return numeros_unicos


def desglosar_ficha_por_telefono(ficha: FichaNegocioLens) -> list[FichaNegocioLens]:
    """Duplica una entidad FichaNegocioLens por cada numero telefonico que contenga.

    Si contiene dos o mas numeros, genera registros duplicados identicos donde
    unicamente cambia el valor de la columna 'telefono'. Si solo contiene uno
    o ninguno, devuelve una lista con la ficha original.
    """
    telefonos = separar_telefonos(ficha.telefono)
    if len(telefonos) <= 1:
        if telefonos:
            ficha.telefono = telefonos[0]
        return [ficha]

    fichas_duplicadas: list[FichaNegocioLens] = []
    for tel in telefonos:
        copia = replace(ficha, telefono=tel)
        fichas_duplicadas.append(copia)
    return fichas_duplicadas


def desglosar_fichas_por_telefono(fichas: list[FichaNegocioLens]) -> list[FichaNegocioLens]:
    """Aplica el desglose y duplicacion por telefono a una coleccion de entidades."""
    resultado: list[FichaNegocioLens] = []
    for ficha in fichas:
        resultado.extend(desglosar_ficha_por_telefono(ficha))
    return resultado


def desglosar_fila_por_telefono(
    fila: dict[str, Any], columna_telefono: str = "telefono"
) -> list[dict[str, Any]]:
    """Duplica una fila tabular (diccionario) cuando contenga multiples telefonos.

    Conserva todas las demas columnas identicas y asigna un solo numero a cada fila resultante.
    """
    valor_raw = str(fila.get(columna_telefono, "") or "")
    telefonos = separar_telefonos(valor_raw)
    if len(telefonos) <= 1:
        copia = dict(fila)
        if telefonos and columna_telefono in copia:
            copia[columna_telefono] = telefonos[0]
        return [copia]

    filas_duplicadas: list[dict[str, Any]] = []
    for tel in telefonos:
        copia = dict(fila)
        copia[columna_telefono] = tel
        filas_duplicadas.append(copia)
    return filas_duplicadas


def desglosar_filas_por_telefono(
    filas: list[dict[str, Any]], columna_telefono: str = "telefono"
) -> list[dict[str, Any]]:
    """Aplica el desglose por telefono a una lista de filas tabulares."""
    resultado: list[dict[str, Any]] = []
    for fila in filas:
        resultado.extend(desglosar_fila_por_telefono(fila, columna_telefono=columna_telefono))
    return resultado


def desglosar_archivo_csv_telefonos(
    ruta_csv_origen: Path | str,
    ruta_csv_destino: Path | str | None = None,
    columna_telefono: str = "telefono",
) -> Path:
    """Lee un archivo CSV, desglosa las filas con multiples telefonos y guarda el resultado."""
    origen = Path(ruta_csv_origen)
    destino = Path(ruta_csv_destino) if ruta_csv_destino else origen

    with open(origen, mode="r", encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        campos = list(lector.fieldnames or [])
        filas = list(lector)

    filas_desglosadas = desglosar_filas_por_telefono(filas, columna_telefono=columna_telefono)

    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, mode="w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(filas_desglosadas)

    return destino


if __name__ == "__main__":
    if len(sys.argv) > 1:
        ruta_archivo = Path(sys.argv[1])
        col_tel = sys.argv[2] if len(sys.argv) > 2 else "telefono"
        if ruta_archivo.is_file():
            salida = desglosar_archivo_csv_telefonos(ruta_archivo, columna_telefono=col_tel)
            print(f"[OK] Archivo CSV desglosado exitosamente: {salida}")
        else:
            print(f"[ERROR] El archivo especificado no existe: {ruta_archivo}")
    else:
        print("[INFO] Uso: python -m procesos_ia.dominio.ia_web.desglosador_telefonos <ruta_csv> [columna_telefono]")
