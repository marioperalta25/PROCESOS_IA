"""Modulo de aplicacion para la persistencia y exportacion de fichas y datos enriquecidos."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from procesos_ia.dominio.ia_web.desglosador_telefonos import (
    desglosar_ficha_por_telefono,
    desglosar_fichas_por_telefono,
    desglosar_filas_por_telefono,
)
from procesos_ia.dominio.ia_web.ficha_negocio import FichaNegocioLens
from procesos_ia.infraestructura.archivos.escritor_csv import guardar_filas_csv

COLUMNAS_FICHA_CSV = [
    "id_registro",
    "estado_ia",
    "propietario",
    "negocio",
    "categoria",
    "telefono",
    "ubicacion",
    "licencia",
    "correo_electronico",
    "sitio_web",
    "idiomas",
    "enlaces_str",
    "texto_sintesis",
    "fuente_imagen",
]


def guardar_auditoria_extraccion_md(
    ruta_md: Path,
    ficha: FichaNegocioLens,
    html_completo: str = "",
) -> Path:
    """Escribe o anexa un registro detallado en formato Markdown para auditoria de extraccion."""
    ruta_md.parent.mkdir(parents=True, exist_ok=True)
    es_nuevo = not ruta_md.exists() or ruta_md.stat().st_size == 0

    marca_tiempo = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    id_reg = ficha.id_registro or "sin_id"
    fuente = ficha.fuente_imagen or "desconocida"

    with open(ruta_md, mode="a", encoding="utf-8") as f:
        if es_nuevo:
            f.write("# Reporte de Auditoria de Extraccion Lens\n\n")
            f.write(f"- Generado el: {marca_tiempo}\n")
            f.write(f"- Archivo: `{ruta_md.name}`\n\n---\n\n")

        f.write(f"## Registro: `{id_reg}`\n\n")
        f.write(f"- **Fecha y hora**: {marca_tiempo}\n")
        f.write(f"- **Fuente / Imagen**: `{fuente}`\n")
        f.write(f"- **Estado IA**: `{ficha.estado_ia}`\n")
        f.write(f"- **Negocio**: {ficha.negocio or 'N/A'}\n")
        f.write(f"- **Propietario**: {ficha.propietario or 'N/A'}\n")
        f.write(f"- **Categoria**: {ficha.categoria or 'N/A'}\n")
        f.write(f"- **Telefono**: {ficha.telefono or 'N/A'}\n")
        f.write(f"- **Ubicacion**: {ficha.ubicacion or 'N/A'}\n")
        f.write(f"- **Licencia**: {ficha.licencia or 'N/A'}\n")
        f.write(f"- **Correo**: {ficha.correo_electronico or 'N/A'}\n")
        f.write(f"- **Sitio web**: {ficha.sitio_web or 'N/A'}\n")
        if ficha.enlaces:
            f.write(f"- **Enlaces**: {' ; '.join(ficha.enlaces)}\n")
        f.write("\n### Sintesis de Texto Extraido:\n\n```text\n")
        f.write((ficha.texto_sintesis or "").strip() + "\n```\n\n")

        html_a_guardar = html_completo or str(ficha.metadatos_adicionales.get("html_completo", ""))
        if html_a_guardar:
            f.write(f"### DOM / HTML Capturado ({len(html_a_guardar)} caracteres):\n\n")
            f.write("<details>\n<summary>Desplegar HTML completo</summary>\n\n```html\n")
            f.write(html_a_guardar.strip() + "\n```\n\n</details>\n\n")

        f.write("---\n\n")

    return ruta_md


def guardar_ficha_individual_csv(
    ficha: FichaNegocioLens,
    directorio_destino: Path,
    nombre_archivo: str | None = None,
    generar_auditoria_md: bool = True,
) -> Path:
    """Guarda una ficha desglosando por telefono en un archivo CSV y opcionalmente su auditoria MD."""
    directorio_destino.mkdir(parents=True, exist_ok=True)
    if not nombre_archivo:
        marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"extraccion_url_{marca_tiempo}.csv"

    ruta_csv = directorio_destino / nombre_archivo
    es_nuevo = not ruta_csv.exists() or ruta_csv.stat().st_size == 0

    fichas_desglosadas = desglosar_ficha_por_telefono(ficha)
    with open(ruta_csv, mode="a", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS_FICHA_CSV, extrasaction="ignore")
        if es_nuevo:
            escritor.writeheader()
        for f_item in fichas_desglosadas:
            escritor.writerow(f_item.a_diccionario(normalizado=True))

    if generar_auditoria_md:
        guardar_auditoria_extraccion_md(ruta_csv.with_suffix(".md"), ficha)
    return ruta_csv


def guardar_fichas_lote_csv(
    fichas: list[FichaNegocioLens],
    ruta_salida: Path,
    modo: str = "sobrescribir",
) -> Path:
    """Guarda una coleccion de fichas desglosando por telefono en el archivo CSV de destino."""
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    es_nuevo = (modo == "sobrescribir") or (not ruta_salida.exists()) or (ruta_salida.stat().st_size == 0)
    modo_apertura = "w" if modo == "sobrescribir" else "a"

    fichas_desglosadas = desglosar_fichas_por_telefono(fichas)
    with open(ruta_salida, mode=modo_apertura, newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS_FICHA_CSV, extrasaction="ignore")
        if es_nuevo:
            escritor.writeheader()
        for f_item in fichas_desglosadas:
            escritor.writerow(f_item.a_diccionario(normalizado=True))

    return ruta_salida


def guardar_filas_enriquecidas_csv(
    filas: list[dict[str, Any]],
    ruta_salida: Path,
    columna_telefono: str = "telefono",
) -> Path:
    """Escribe filas tabulares enriquecidas desglosando por telefono y preservando columnas."""
    if not filas:
        return ruta_salida

    col_tel = columna_telefono
    if filas and col_tel not in filas[0]:
        for k in filas[0].keys():
            if k.lower().strip() in {"telefono", "telefonos", "tel", "celular", "phone"}:
                col_tel = k
                break

    filas_desglosadas = desglosar_filas_por_telefono(filas, columna_telefono=col_tel)

    return guardar_filas_csv(filas_desglosadas, ruta_salida)


def guardar_auditoria_modo_ia_md(
    ruta_md: Path,
    n_lote: int,
    total_lotes: int,
    fila_desde: int,
    fila_hasta: int,
    entrada_prompt: str,
    respuesta_ia: str,
    duracion_seg: float = 0.0,
    prompt_inicial: str = "",
    html_crudo: str = "",
) -> None:
    """Anexa de forma opcional y protegida una entrada de inspeccion con HTML crudo para Modo IA."""
    try:
        ruta_md.parent.mkdir(parents=True, exist_ok=True)
        es_nuevo = not ruta_md.exists() or ruta_md.stat().st_size == 0
        marca = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(ruta_md, mode="a", encoding="utf-8") as f:
            if es_nuevo:
                f.write(f"# Reporte de Inspeccion Modo IA\n\n- Fecha: {marca}\n\n")
                if prompt_inicial:
                    f.write(f"## Prompt Inicial del Sistema\n\n```text\n{prompt_inicial.strip()}\n```\n\n---\n\n")
                f.write("## Bitacora de Lotes\n\n")
            if entrada_prompt or respuesta_ia or html_crudo:
                bloque_html = ""
                if html_crudo:
                    bloque_html = f"**HTML Crudo del DOM ({len(html_crudo)} caracteres):**\n<details>\n<summary>Desplegar HTML del Turno</summary>\n\n```html\n{html_crudo.strip()}\n```\n\n</details>\n\n"
                f.write(
                    f"### Lote {n_lote}/{total_lotes} (Filas {fila_desde}-{fila_hasta}) - {duracion_seg:.1f}s\n\n"
                    f"**Entrada Enviada:**\n```text\n{entrada_prompt.strip()}\n```\n\n"
                    f"**Respuesta Capturada del DOM:**\n```text\n{respuesta_ia.strip()}\n```\n\n"
                    f"{bloque_html}"
                    f"---\n\n"
                )
    except Exception:
        pass
