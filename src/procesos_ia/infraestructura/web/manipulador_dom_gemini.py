"""Manipulador DOM para Gemini Web (https://gemini.google.com/app)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path
import re
from typing import Any

logger = logging.getLogger(__name__)

JS_SCROLL_FONDO = """
(() => {
    try {
        const scroller = document.querySelector('#chat-history') ||
                         document.querySelector('.chat-history-scroll-container') ||
                         document.querySelector('infinite-scroller');
        if (scroller) scroller.scrollTop = scroller.scrollHeight;
        const convs = document.querySelectorAll('.conversation-container, model-response, user-query');
        if (convs.length > 0) convs[convs.length - 1].scrollIntoView({ behavior: 'smooth', block: 'end' });
    } catch(e) {}
})()
"""

JS_ACEPTAR_DIALOGOS = """
(() => {
    const btn = document.querySelector('button[data-test-id="upload-image-agree-button"]') ||
                document.querySelector('button[aria-label*="Acepto"]') ||
                document.querySelector('button[aria-label*="Agree"]');
    if (btn) { btn.click(); return true; }
    return false;
})()
"""

JS_NUEVA_CONVERSACION = """
(() => {
    const btn = document.querySelector('[data-test-id="new-chat-button"]') ||
                document.querySelector('button[aria-label*="Nuevo chat"]') ||
                document.querySelector('button[aria-label*="New chat"]');
    if (btn) { btn.click(); return true; }
    return false;
})()
"""


from procesos_ia.infraestructura.web.extractor_json import extraer_y_reparar_json


async def iniciar_nuevo_chat_gemini(pestana: Any) -> bool:
    """Inicia una nueva sesión limpia en Gemini Web."""
    try:
        clicado = await pestana.evaluate(JS_NUEVA_CONVERSACION)
        if clicado and not hasattr(clicado, "exception"):
            await asyncio.sleep(1.5)
            return True
        await pestana.reload()
        await asyncio.sleep(2.5)
        return True
    except Exception as error:
        logger.warning("[ALERTA] Fallo al iniciar nuevo chat en Gemini: %s", error)
        return False


async def enviar_prompt_gemini(
    pestana: Any,
    prompt: str,
    ruta_imagen: Path | None = None,
) -> bool:
    """Inyecta el prompt (y opcionalmente una imagen) y dispara el envío en Gemini."""
    base64_data = ""
    if ruta_imagen and ruta_imagen.exists():
        with open(ruta_imagen, "rb") as archivo:
            b64_str = base64.b64encode(archivo.read()).decode("utf-8")
            base64_data = f"data:image/jpeg;base64,{b64_str}"

    js_inyeccion = f"""
    (async () => {{
        try {{
            const base64Data = {json.dumps(base64_data)};
            const promptText = {json.dumps(prompt)};

            const editor = document.querySelector('div[contenteditable="true"], rich-textarea div[role="textbox"], .qs-textarea');
            if (!editor) return "NO_EDITOR";
            editor.focus();

            if (base64Data && base64Data.length > 0) {{
                const fetchRes = await fetch(base64Data);
                const blob = await fetchRes.blob();
                const dataTransfer = new DataTransfer();
                const file = new File([blob], "imagen.jpg", {{ type: "image/jpeg" }});
                dataTransfer.items.add(file);

                const pasteEvent = new ClipboardEvent('paste', {{
                    clipboardData: dataTransfer,
                    bubbles: true,
                    cancelable: true
                }});
                editor.dispatchEvent(pasteEvent);
                await new Promise(r => setTimeout(r, 800));
            }}

            editor.innerText = promptText;
            editor.dispatchEvent(new InputEvent('input', {{ bubbles: true, cancelable: true }}));
            return "OK";
        }} catch (e) {{
            return e.toString();
        }}
    }})()
    """
    res = await pestana.evaluate(js_inyeccion)
    if isinstance(res, str) and "NO_EDITOR" in res:
        logger.error("[ERROR] Editor de Gemini no encontrado en el DOM")
        return False

    if base64_data:
        await asyncio.sleep(2.0)
        try:
            await pestana.evaluate(JS_ACEPTAR_DIALOGOS)
        except Exception:
            pass

    await pestana.evaluate(JS_SCROLL_FONDO)

    js_clic_enviar = """
    (() => {
        const sendBtn = document.querySelector('button[aria-label*="Enviar"]') ||
                        document.querySelector('button[aria-label*="Send"]') ||
                        document.querySelector('button .mat-icon[fonticon="arrow_upward"]')?.closest('button') ||
                        document.querySelector('button.send-button');
        if (sendBtn && !sendBtn.disabled) {
            sendBtn.click();
            return true;
        }
        return false;
    })()
    """
    enviado = await pestana.evaluate(js_clic_enviar)
    if not enviado or hasattr(enviado, "exception"):
        # Respaldo: Presionar Enter en el editor
        js_enter = """
        (() => {
            const editor = document.querySelector('div[contenteditable="true"], rich-textarea div[role="textbox"]');
            if (editor) {
                editor.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
                return true;
            }
            return false;
        })()
        """
        await pestana.evaluate(js_enter)

    await pestana.evaluate(JS_SCROLL_FONDO)
    return True


async def esperar_respuesta_gemini(
    pestana: Any,
    tiempo_limite: int = 45,
    intervalo_estabilidad: float = 1.0,
) -> str | None:
    """Espera que Gemini complete la generación y retorna el texto extraído."""
    js_verificar_estado = """
    (() => {
        const generando = document.querySelector('mat-icon[fonticon="stop"]') ||
                          document.querySelector('button[aria-label*="Detener"]') ||
                          document.querySelector('.stop-button');
        const codeElems = document.querySelectorAll('code[data-test-id="code-content"], code-block code, code.code-container');
        if (codeElems.length > 0) {
            return {
                generando: !!generando,
                texto: (codeElems[codeElems.length - 1].innerText || "").trim(),
                es_codigo: true
            };
        }
        const respElems = document.querySelectorAll('.model-response-text, .response-container, message-content');
        if (respElems.length > 0) {
            return {
                generando: !!generando,
                texto: (respElems[respElems.length - 1].innerText || "").trim(),
                es_codigo: false
            };
        }
        return { generando: !!generando, texto: "", es_codigo: false };
    })()
    """
    inicio = asyncio.get_event_loop().time()
    ultimo_texto = ""
    contador_estable = 0

    while (asyncio.get_event_loop().time() - inicio) < tiempo_limite:
        await pestana.evaluate(JS_SCROLL_FONDO)
        try:
            estado = await pestana.evaluate(js_verificar_estado)
        except Exception:
            estado = None

        if isinstance(estado, dict):
            generando = estado.get("generando", False)
            texto_actual = str(estado.get("texto", "")).strip()

            if texto_actual:
                if texto_actual == ultimo_texto and not generando:
                    contador_estable += 1
                    if contador_estable >= 2:
                        return texto_actual
                else:
                    ultimo_texto = texto_actual
                    contador_estable = 0

        await asyncio.sleep(intervalo_estabilidad)

    return ultimo_texto if ultimo_texto else None
