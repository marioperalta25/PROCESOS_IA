"""Inyector de imagenes en base64 y prompts para Modo IA de Google."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any

from procesos_ia.infraestructura.web.conversacional.manipulador_dom_modo_ia import (
    esperar_input_modo_ia,
    pegar_texto_en_elemento,
)

logger = logging.getLogger(__name__)


def serializar_imagen_a_base64(ruta_imagen: Path) -> tuple[str, str, str]:
    """Lee el archivo de imagen en disco y lo serializa a base64 con su MIME type."""
    if not ruta_imagen.is_file():
        raise FileNotFoundError(f"Archivo de imagen no encontrado: {ruta_imagen}")

    mime, _ = mimetypes.guess_type(str(ruta_imagen))
    tipo_mime = mime or "image/jpeg"
    with open(ruta_imagen, "rb") as f:
        datos_b64 = base64.b64encode(f.read()).decode("utf-8")
    data_uri = f"data:{tipo_mime};base64,{datos_b64}"
    return data_uri, tipo_mime, ruta_imagen.name


async def inyectar_imagen_y_prompt_modo_ia(
    pestana: Any,
    prompt: str,
    ruta_imagen: Path | None = None,
    timeout_input: float = 15.0,
) -> bool:
    """Adjunta una imagen via base64/ClipboardEvent y envia el prompt en Modo IA."""
    elem_input = await esperar_input_modo_ia(pestana, timeout_segundos=timeout_input)
    if elem_input is None:
        logger.warning("[ALERTA] No se encontro campo de entrada en Modo IA para inyectar imagen")
        return False

    if ruta_imagen is not None and ruta_imagen.is_file():
        data_uri, tipo_mime, nombre_archivo = serializar_imagen_a_base64(ruta_imagen)
        js_adjuntar = f"""
        (async () => {{
            try {{
                const dataUri = {json.dumps(data_uri)};
                const fileName = {json.dumps(nombre_archivo)};
                const mimeType = {json.dumps(tipo_mime)};

                const fetchRes = await fetch(dataUri);
                const blob = await fetchRes.blob();
                const file = new File([blob], fileName, {{ type: mimeType }});

                const dt = new DataTransfer();
                dt.items.add(file);

                const fileInputs = Array.from(document.querySelectorAll('input[type="file"]'));
                for (const fi of fileInputs) {{
                    try {{
                        fi.files = dt.files;
                        fi.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return "ATTACHED_VIA_INPUT";
                    }} catch (e) {{}}
                }}

                const target = document.querySelector("textarea.ITIRGe")
                    || document.querySelector("textarea[aria-label*='pregunta']")
                    || document.querySelector("textarea.gLFyf")
                    || document.querySelector("div[contenteditable='true']")
                    || document.querySelector("textarea")
                    || document.body;

                if (target) {{
                    if (typeof target.focus === "function") {{
                        target.focus();
                    }}
                    const pasteEvt = new ClipboardEvent('paste', {{
                        clipboardData: dt,
                        bubbles: true,
                        cancelable: true
                    }});
                    target.dispatchEvent(pasteEvt);
                    return "ATTACHED_VIA_PASTE";
                }}
                return "NO_TARGET_FOUND";
            }} catch (err) {{
                return "ERROR: " + err.toString();
            }}
        }})()
        """
        try:
            res_adj = await pestana.evaluate(js_adjuntar)
            logger.info("[INFO] Estado de inyección de imagen: %s", res_adj)
            await asyncio.sleep(1.8)
        except Exception as err:
            logger.warning("[ALERTA] Error al ejecutar inyección de imagen: %s", err)

    if not await pegar_texto_en_elemento(pestana, elem_input, prompt):
        return False
    await asyncio.sleep(0.3)

    js_submit = """
    (() => {
        for (const s of [
            "button[aria-label*='Enviar']", "button[aria-label*='Send']",
            "button[data-xid*='send']", "button.wdK4Nc", "button[jsname='w019Fc']",
            "cr-composebox-submit", "button[type='submit']"
        ]) {
            const el = document.querySelector(s);
            if (el && (el.offsetWidth > 0 || el.offsetHeight > 0)) {
                el.click();
                return "selector_submit";
            }
        }
        const ta = document.querySelector("textarea.ITIRGe, textarea[name='q'], textarea");
        if (ta) {
            ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
            return "enter_textarea";
        }
        return null;
    })()
    """
    try:
        res_submit = await pestana.evaluate(js_submit)
        return bool(res_submit)
    except Exception as err:
        logger.error("[ERROR] Fallo al despachar envío de Modo IA con imagen: %s", err)
        return False

