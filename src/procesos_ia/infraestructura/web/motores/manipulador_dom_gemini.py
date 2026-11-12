"""Manipulador DOM para Gemini Web (https://gemini.google.com/app)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path
import re
from typing import Any, Callable

logger = logging.getLogger(__name__)

JS_SCROLL_FONDO = """(() => {
    try {
        const scroller = document.querySelector('#chat-history') ||
                         document.querySelector('.chat-history-scroll-container') ||
                         document.querySelector('infinite-scroller');
        if (scroller) scroller.scrollTop = scroller.scrollHeight;
        const convs = document.querySelectorAll('.conversation-container, model-response, user-query');
        if (convs.length > 0) convs[convs.length - 1].scrollIntoView({ behavior: 'smooth', block: 'end' });
    } catch(e) {}
})()"""

JS_ACEPTAR_DIALOGOS = """(() => {
    const btn = document.querySelector('button[data-test-id="upload-image-agree-button"]') ||
                document.querySelector('button[aria-label*="Acepto"]') ||
                document.querySelector('button[aria-label*="Agree"]');
    if (btn) { btn.click(); return true; }
    return false;
})()"""

JS_NUEVA_CONVERSACION = """(() => {
    const btn = document.querySelector('[data-test-id="new-chat-button"]') ||
                document.querySelector('button[aria-label*="Nuevo chat"]') ||
                document.querySelector('button[aria-label*="New chat"]');
    if (btn) { btn.click(); return true; }
    return false;
})()"""


from procesos_ia.infraestructura.web.base.extractor_json import extraer_y_reparar_json


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


async def esperar_editor_gemini(pestana: Any, timeout: float = 25.0) -> bool:
    """Espera activamente a que el editor DOM de Gemini esté montado y listo."""
    js_check = """
    (() => {
        const editor = document.querySelector('div[contenteditable="true"], rich-textarea div[role="textbox"], .qs-textarea');
        return !!editor;
    })()
    """
    inicio = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - inicio) < timeout:
        try:
            listo = await pestana.evaluate(js_check)
            if listo and not hasattr(listo, "exception"):
                return True
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return False


async def enviar_prompt_gemini(
    pestana: Any,
    prompt: str,
    ruta_imagen: Path | None = None,
) -> bool:
    """Inyecta el prompt e imagen con DataTransfer sincronizado y verificación en Gemini Web."""
    listo = await esperar_editor_gemini(pestana, timeout=20.0)
    if not listo:
        logger.error("[ERROR] Editor de Gemini no disponible tras tiempo de espera")
        return False

    if ruta_imagen and ruta_imagen.exists():
        with open(ruta_imagen, "rb") as archivo:
            b64_str = base64.b64encode(archivo.read()).decode("utf-8")
            base64_data = f"data:image/jpeg;base64,{b64_str}"

        # Inyección atómica sincronizada de imagen y texto (patrón TSUKUYOMI probado)
        js_inyectar_conjunto = f"""
        (async () => {{
            try {{
                const base64Data = {json.dumps(base64_data)};
                const promptText = {json.dumps(prompt)};

                const fetchRes = await fetch(base64Data);
                const blob = await fetchRes.blob();

                const dataTransfer = new DataTransfer();
                const file = new File([blob], "{ruta_imagen.name}", {{ type: "image/jpeg" }});
                dataTransfer.items.add(file);

                const editor = document.querySelector('div[contenteditable="true"], rich-textarea div[role="textbox"], .qs-textarea');
                if (!editor) return "NO_EDITOR";

                editor.focus();

                const pasteEvent = new ClipboardEvent('paste', {{
                    clipboardData: dataTransfer,
                    bubbles: true,
                    cancelable: true
                }});
                editor.dispatchEvent(pasteEvent);

                await new Promise(r => setTimeout(r, 600));

                const pElem = editor.querySelector('p');
                if (pElem) {{
                    pElem.innerText = promptText;
                }} else {{
                    editor.innerText = promptText;
                }}
                editor.dispatchEvent(new InputEvent('input', {{ bubbles: true, cancelable: true }}));

                return "OK";
            }} catch (e) {{
                return "ERROR: " + e.toString();
            }}
        }})()
        """
        try:
            res_iny = await pestana.evaluate(js_inyectar_conjunto, await_promise=True)
            res_str = str(res_iny) if res_iny is not None else ""
            if "OK" not in res_str:
                logger.error("[ERROR] Fallo al inyectar imagen y prompt en Gemini: %s", res_iny)
                return False
        except Exception as err_iny:
            logger.error("[ERROR] Excepcion al inyectar imagen en Gemini: %s", err_iny)
            return False

        # Espera de seguridad para que Gemini procese el thumbnail de la imagen
        await asyncio.sleep(2.5)
        try:
            await pestana.evaluate(JS_ACEPTAR_DIALOGOS)
        except Exception:
            pass

    else:
        # Envío solo de texto
        js_solo_texto = f"""
        (() => {{
            try {{
                const promptText = {json.dumps(prompt)};
                const editor = document.querySelector('div[contenteditable="true"], rich-textarea div[role="textbox"], .qs-textarea');
                if (!editor) return "NO_EDITOR";

                editor.focus();
                const pElem = editor.querySelector('p');
                if (pElem) {{
                    pElem.innerText = promptText;
                }} else {{
                    editor.innerText = promptText;
                }}
                editor.dispatchEvent(new InputEvent('input', {{ bubbles: true, cancelable: true }}));
                return "PROMPT_OK";
            }} catch(e) {{
                return "ERROR: " + e.toString();
            }}
        }})()
        """
        res_txt = await pestana.evaluate(js_solo_texto)
        if isinstance(res_txt, str) and "NO_EDITOR" in res_txt:
            logger.error("[ERROR] Editor de Gemini no encontrado para envio de texto")
            return False
        await asyncio.sleep(0.8)

    await pestana.evaluate(JS_SCROLL_FONDO)

    # Disparo de envío: botón de envío con respaldo Enter
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
    tiempo_limite: int = 90,
    intervalo_estabilidad: float = 1.0,
    verificador_cancelacion: Callable[[], bool] | None = None,
) -> str | None:
    """Espera y extrae la respuesta de Gemini con deteccion reactiva de cancelacion."""
    js_extract_code_response = """
    JSON.stringify((() => {
        try {
            const stopIcon = document.querySelector('mat-icon[fonticon="stop"]') ||
                             document.querySelector('button[aria-label*="Detener"]') ||
                             document.querySelector('.stop-button');
            if (stopIcon) return { isGenerating: true, text: "" };
            const codeElems = Array.from(document.querySelectorAll('code[data-test-id="code-content"], code-block code, code.code-container, pre code, pre'));
            if (codeElems.length > 0) {
                const latestCode = codeElems[codeElems.length - 1];
                const codeText = (latestCode.innerText || "").trim();
                if (codeText.length > 15) return { isGenerating: false, text: codeText, method: "LATEST_CODE_BLOCK_DIRECT" };
            }
            const modelResps = Array.from(document.querySelectorAll('model-response, .model-response-text, .response-container, message-content, .markdown'));
            if (modelResps.length > 0) {
                const latestModel = modelResps[modelResps.length - 1];
                const modelText = (latestModel.innerText || "").trim();
                if (modelText.length > 15) return { isGenerating: false, text: modelText, method: "LATEST_MODEL_RESPONSE" };
            }
            return { isGenerating: false, text: "" };
        } catch(e) {
            return { isGenerating: false, error: e.toString(), text: "" };
        }
    })())
    """
    inicio = asyncio.get_event_loop().time()
    ultimo_texto, contador_estable = "", 0

    while (asyncio.get_event_loop().time() - inicio) < tiempo_limite:
        if verificador_cancelacion and verificador_cancelacion():
            return None
        try:
            await pestana.evaluate(JS_SCROLL_FONDO)
            res_val = await pestana.evaluate(js_extract_code_response)
            if isinstance(res_val, dict):
                res = res_val
            elif res_val and not hasattr(res_val, "exception"):
                res = json.loads(str(res_val))
            else:
                res = {}
        except Exception:
            if verificador_cancelacion and verificador_cancelacion():
                return None
            res = {}

        if res.get("isGenerating") or res.get("generando"):
            contador_estable = 0
            for _ in range(max(1, int(intervalo_estabilidad / 0.1))):
                if verificador_cancelacion and verificador_cancelacion():
                    return None
                await asyncio.sleep(0.1)
            continue

        texto = str(res.get("text") or res.get("texto") or "").strip()
        if texto and len(texto) >= 10:
            if "{" in texto and "}" in texto:
                if res.get("es_codigo") or res.get("method") == "LATEST_CODE_BLOCK_DIRECT":
                    return texto
                if texto == ultimo_texto:
                    contador_estable += 1
                    if contador_estable >= 2:
                        return texto
                else:
                    ultimo_texto, contador_estable = texto, 1

        for _ in range(max(1, int(intervalo_estabilidad / 0.1))):
            if verificador_cancelacion and verificador_cancelacion():
                return None
            await asyncio.sleep(0.1)

    return ultimo_texto if ultimo_texto else None
