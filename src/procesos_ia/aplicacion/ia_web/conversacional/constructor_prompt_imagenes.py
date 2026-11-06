"""Constructor y formateador de prompts para extraccion de datos desde imagenes en Modo Chat."""

from __future__ import annotations

import json
from typing import Any

CAMPOS_DISPONIBLES: dict[str, dict[str, str]] = {
    "negocio": {
        "etiqueta": "Nombre del Negocio",
        "descripcion": "Nombre comercial exacto de la empresa o negocio.",
        "ejemplo": "Ejemplo Carpentry LLC",
    },
    "telefonos": {
        "etiqueta": "Teléfonos (con desglose)",
        "descripcion": "Número(s) de teléfono detectados. Si hay más de uno, sepáralos obligatoriamente por ' / '.",
        "ejemplo": "555-123-4567 / 555-987-6543",
    },
    "owner": {
        "etiqueta": "Propietario / Owner",
        "descripcion": "Nombre del propietario, dueño o persona de contacto principal.",
        "ejemplo": "John Doe",
    },
    "address": {
        "etiqueta": "Dirección / Address",
        "descripcion": "Dirección física, calle, ciudad o estado donde opera.",
        "ejemplo": "123 Main St, Miami, FL",
    },
    "habla_espanol": {
        "etiqueta": "Habla Espanol",
        "descripcion": "Si la imagen contiene textos en español o anuncia atención en español, responde obligatoriamente 'habla espanol' (con n); de lo contrario responde 'No'.",
        "ejemplo": "habla espanol",
    },
}

COLUMNAS_BASE_IMAGEN = ["id_registro", "archivo_imagen", "estado_ia"]


def construir_prompt_extraccion_imagen(
    campos_activos: list[str] | tuple[str, ...] | dict[str, bool],
    instrucciones_adicionales: str = "",
) -> tuple[str, list[str]]:
    """Construye el prompt estructurado en JSON según las casillas seleccionadas por el usuario."""
    if isinstance(campos_activos, dict):
        claves = [k for k, v in campos_activos.items() if v and k in CAMPOS_DISPONIBLES]
    else:
        claves = [k for k in campos_activos if k in CAMPOS_DISPONIBLES]

    if not claves:
        claves = ["negocio", "telefonos"]

    lineas_campos: list[str] = []
    ejemplo_json: dict[str, str] = {}
    for c in claves:
        info = CAMPOS_DISPONIBLES[c]
        lineas_campos.append(f"- {c}: {info['descripcion']}")
        ejemplo_json[c] = info["ejemplo"]

    bloque_campos = "\n".join(lineas_campos)
    bloque_json = json.dumps(ejemplo_json, ensure_ascii=False, indent=2)

    extra_txt = ""
    if instrucciones_adicionales and instrucciones_adicionales.strip():
        extra_txt = f"\nINSTRUCCIONES ADICIONALES:\n{instrucciones_adicionales.strip()}\n"

    prompt = (
        "Analiza detalladamente la imagen adjunta y extrae la información comercial visible.\n\n"
        f"CAMPOS REQUERIDOS:\n{bloque_campos}\n"
        f"{extra_txt}\n"
        "REGLAS DE FORMATO:\n"
        "1. Responde estrictamente un único objeto JSON válido con las claves solicitadas.\n"
        f"{bloque_json}\n"
        "2. Si algún dato no es visible o legible en la imagen, asigna el valor exacto \"ND\".\n"
        "3. Si detectas múltiples teléfonos, sepáralos únicamente con \" / \".\n"
        "4. Responde únicamente el bloque JSON, sin texto introductorio ni explicaciones."
    )

    columnas_salida = COLUMNAS_BASE_IMAGEN + [c for c in claves if c not in COLUMNAS_BASE_IMAGEN]
    return prompt.strip(), columnas_salida

