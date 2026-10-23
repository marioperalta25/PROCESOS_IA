"""Modulo de normalizacion de textos y datos para inferencia de modelos IA."""

from __future__ import annotations

import re
from typing import Any
import unicodedata


def reemplazar_enies(texto: str) -> str:
    """Reemplaza caracteres enie por n/N tanto en formato compuesto como descompuesto."""
    if not texto:
        return ""
    # Reemplazo de caracteres directos precompuestos
    resultado = texto.replace("ñ", "n").replace("Ñ", "N")
    # Manejo de caracteres enies descompuestos NFD (n + combinacion de tilde ~)
    resultado = resultado.replace("n\u0303", "n").replace("N\u0303", "N")
    resultado = resultado.replace("n\u0301", "n").replace("N\u0301", "N")
    return resultado


def quitar_acentos(texto: str) -> str:
    """Elimina marcas diacriticas y tildes conservando los caracteres alfanumericos base."""
    if not texto:
        return ""
    # Primero se asegura el reemplazo explicito de enies para evitar perdida de contexto
    texto_sin_enie = reemplazar_enies(texto)
    # Descomposicion NFD para separar caracteres base de sus acentos diacriticos
    descompuesto = unicodedata.normalize("NFD", texto_sin_enie)
    # Filtrar marcas de combinacion de acento (categoria Mn = Nonspacing_Mark)
    filtrado = "".join(caracter for caracter in descompuesto if unicodedata.category(caracter) != "Mn")
    # Retornar en forma normalizada NFC
    return unicodedata.normalize("NFC", filtrado)


def limpiar_espacios(texto: str) -> str:
    """Normaliza espacios continuos, tabuladores y saltos redundantes a un unico espacio."""
    if not texto:
        return ""
    # Reemplazar espacios no divisibles y tabulaciones
    limpio = re.sub(r"[\t\r\n\u00a0\u200b]+", " ", texto)
    # Colapsar multiples espacios a uno solo
    limpio = re.sub(r" {2,}", " ", limpio)
    return limpio.strip()


def normalizar_texto(
    texto: str,
    cambiar_enies: bool = True,
    quitar_tildes: bool = True,
    limpiar_espacios_extra: bool = True,
) -> str:
    """Aplica la secuencia de saneamiento y normalizacion a un texto de entrada."""
    if not isinstance(texto, str):
        return str(texto)
    resultado = texto
    if cambiar_enies:
        resultado = reemplazar_enies(resultado)
    if quitar_tildes:
        resultado = quitar_acentos(resultado)
    if limpiar_espacios_extra:
        resultado = limpiar_espacios(resultado)
    return resultado


def normalizar_datos_modelo(datos: Any) -> Any:
    """Normaliza recursivamente cadenas de texto en diccionarios, listas y valores escalares.

    Conserva las claves de los diccionarios intactas para garantizar la correspondencia
    con los nombres de columnas y esquemas del sistema.
    """
    if isinstance(datos, str):
        return normalizar_texto(datos)
    if isinstance(datos, dict):
        return {clave: normalizar_datos_modelo(valor) for clave, valor in datos.items()}
    if isinstance(datos, list):
        return [normalizar_datos_modelo(elemento) for elemento in datos]
    if isinstance(datos, tuple):
        return tuple(normalizar_datos_modelo(elemento) for elemento in datos)
    return datos


def normalizar_clave_comparacion(texto: str) -> str:
    """Convierte texto a minusculas, sin enies ni acentos para comparaciones uniformes."""
    if not texto:
        return ""
    base = normalizar_texto(texto)
    return base.strip().casefold()


def formatear_columnas_delimitadas(
    valores: dict[str, Any],
    columnas: tuple[str, ...] | list[str] | None = None,
    delimitador: str = " | ",
) -> str:
    """Formatea columnas con delimitador | para reconocimiento inequivoco en LLMs.

    Si hay una sola columna, retorna su valor directamente normalizado.
    Si hay dos o mas columnas, retorna 'columna_1: valor_1 | columna_2: valor_2'.
    """
    cols = list(columnas) if columnas is not None else list(valores.keys())
    if not cols:
        return ""
    if len(cols) == 1:
        val = valores.get(cols[0], "")
        return normalizar_texto(str(val) if val is not None else "")

    partes: list[str] = []
    for col in cols:
        val = valores.get(col, "")
        val_norm = normalizar_texto(str(val) if val is not None else "")
        partes.append(f"{col}: {val_norm}")
    return delimitador.join(partes)
