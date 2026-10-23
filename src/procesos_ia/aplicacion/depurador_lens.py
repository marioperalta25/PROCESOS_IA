"""Modulo temporal de depuracion para registrar extracciones de Google Lens en Markdown."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from procesos_ia.dominio.ficha_negocio import FichaNegocioLens

LIMITE_MAX_BYTES = 3 * 1024 * 1024  # 3 MB maximo


def registrar_depuracion_lens(
    destino_dir: Path,
    fuente_imagen: str,
    texto_crudo: str,
    txt_html: str,
    ficha: FichaNegocioLens,
) -> Path:
    """Registra en un archivo Markdown de diagnostico el contenido parseado."""
    destino_dir.mkdir(parents=True, exist_ok=True)
    archivo_md = destino_dir / "depuracion_lens.md"

    if archivo_md.is_file() and archivo_md.stat().st_size > LIMITE_MAX_BYTES:
        try:
            archivo_md.write_text("# Bitacora de Depuracion de Google Lens\n\n", encoding="utf-8")
        except Exception:
            pass

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nombre_img = Path(fuente_imagen).name

    seccion = [
        f"## [{ahora}] Imagen: {nombre_img}",
        f"- **Ruta**: `{fuente_imagen}`",
        f"- **Estado IA**: `{ficha.estado_ia}`",
        "",
        "### Datos Estructurados Finales",
        "```json",
        json.dumps(ficha.a_diccionario(normalizado=True), indent=2, ensure_ascii=False),
        "```",
        "",
        "### Texto Respuesta (Nodriver / DOM)",
        "```text",
        texto_crudo.strip() or "[VACIO]",
        "```",
        "",
        "### Texto Limpio Extraido con BeautifulSoup",
        "```text",
        txt_html.strip() or "[VACIO]",
        "```",
        "",
        "---",
        "",
    ]

    try:
        with open(archivo_md, "a", encoding="utf-8") as f:
            f.write("\n".join(seccion) + "\n")
    except Exception:
        pass

    return archivo_md
