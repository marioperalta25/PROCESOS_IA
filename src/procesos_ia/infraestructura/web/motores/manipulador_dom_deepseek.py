"""Manipulador DOM para DeepSeek Web (https://chat.deepseek.com/)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path
import re
from typing import Any, Callable

logger = logging.getLogger(__name__)

JS_SCROLL_FONDO_DEEPSEEK = """
(() => {
    try {
        const scrollers = document.querySelectorAll('.ds-scroll-area, ._3586175, ._6d215eb, main');
        scrollers.forEach(s => s.scrollTop = s.scrollHeight);
        window.scrollTo(0, document.body.scrollHeight);
        const msgs = document.querySelectorAll('.ds-assistant-message-main-content, ._4f9bf79, .ds-message');
        if (msgs.length > 0) msgs[msgs.length - 1].scrollIntoView({ behavior: 'smooth', block: 'end' });
    } catch(e) {}
})()
"""

JS_NUEVO_CHAT_DEEPSEEK = """
(() => {
    const btn = Array.from(document.querySelectorAll('div, span, button, a'))
        .find(el => el.innerText && el.innerText.trim().toLowerCase() === "nuevo chat");
    if (btn) {
        (btn.closest('div[role="button"], div[tabindex="0"], button, ._5a8ac7a') || btn).click();
        return true;
    }
    return false;
})()
"""


async def iniciar_nuevo_chat_deepseek(pestana: Any) -> bool:
    """Navega a un nuevo chat limpio en DeepSeek Web."""
    try:
        await pestana.get("https://chat.deepseek.com/")
        await asyncio.sleep(2.0)
        return True
    except Exception as error:
        logger.warning("[ALERTA] Navegacion directa fallo, intentando clic en DOM: %s", error)
        try:
            clicado = await pestana.evaluate(JS_NUEVO_CHAT_DEEPSEEK)
            if clicado and not hasattr(clicado, "exception"):
                await asyncio.sleep(1.5)
                return True
        except Exception:
            pass
        return False


PALABRAS_DESCARTAR_NOMBRE = {
    "json", "javascript", "python", "code", "copiar", "descargar", "código",
    "nd", "none", "null", "nan", "markdown", "pre", "text"
}


def extraer_datos_de_texto_plano(texto: str) -> dict[str, Any]:
    """Extrae heurísticamente datos si DeepSeek responde en texto libre sin bloque JSON."""
    telefonos = re.findall(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", texto)
    tels_unicos = list(dict.fromkeys([t.strip() for t in telefonos if t.strip()]))
    nombre = "ND"
    lineas = [l.strip() for l in texto.split("\n") if l.strip() and not l.startswith("```")]
    if lineas:
        candidatos = [
            l.replace("*", "").replace("#", "").strip()
            for l in lineas[:6]
            if len(l) < 60 and l.lower().strip() not in PALABRAS_DESCARTAR_NOMBRE
        ]
        if candidatos:
            nombre = candidatos[0]
    return {
        "nombre_negocio": nombre,
        "owner": "ND",
        "telefonos": tels_unicos,
        "actividades_ingles": ["Business Service"],
        "categoria_principal": "Services",
        "ubicacion_inferida": "ND",
    }


async def esperar_editor_deepseek(pestana: Any, timeout: float = 25.0) -> bool:
    """Espera activamente a que el editor DOM de DeepSeek esté presente y listo."""
    js_check = """
    (() => {
        const ta = document.querySelector('textarea.d96f2d2a, textarea._27c9245, textarea[placeholder*="DeepSeek"], textarea[name="search"], textarea');
        const fileInp = document.querySelector('input[type="file"]');
        return !!(ta || fileInp);
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


async def enviar_prompt_deepseek(
    pestana: Any,
    prompt: str,
    ruta_imagen: Path | None = None,
) -> bool:
    """Inyecta prompt e imagen verificando que la imagen se haya adjuntado antes de enviar."""
    listo = await esperar_editor_deepseek(pestana, timeout=20.0)
    if not listo:
        logger.error("[ERROR] Editor de DeepSeek no disponible tras tiempo de espera")
        return False

    if ruta_imagen and ruta_imagen.exists():
        with open(ruta_imagen, "rb") as archivo:
            b64_str = base64.b64encode(archivo.read()).decode("utf-8")
            base64_data = f"data:image/jpeg;base64,{b64_str}"

        js_adjuntar_imagen = f"""
        (async () => {{
            try {{
                const base64Data = {json.dumps(base64_data)};
                const fetchRes = await fetch(base64Data);
                const blob = await fetchRes.blob();
                const file = new File([blob], "{ruta_imagen.name}", {{ type: "image/jpeg" }});

                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);

                const fileInput = document.querySelector('input[type="file"]');
                if (fileInput) {{
                    fileInput.files = dataTransfer.files;
                    fileInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return "ATTACHED_VIA_FILE_INPUT";
                }}

                const textarea = document.querySelector('textarea.d96f2d2a, textarea._27c9245, textarea[placeholder*="DeepSeek"], textarea[name="search"], textarea');
                if (textarea) {{
                    textarea.focus();
                    const pasteEvent = new ClipboardEvent('paste', {{
                        clipboardData: dataTransfer,
                        bubbles: true,
                        cancelable: true
                    }});
                    textarea.dispatchEvent(pasteEvent);
                    return "ATTACHED_VIA_PASTE_EVENT";
                }}
                return "NO_INPUT_FOUND";
            }} catch(e) {{
                return "ERROR: " + e.toString();
            }}
        }})()
        """
        try:
            res_adj = await pestana.evaluate(js_adjuntar_imagen, await_promise=True)
            res_str = str(res_adj) if res_adj else ""
            if not ("ATTACHED_VIA_FILE_INPUT" in res_str or "ATTACHED_VIA_PASTE_EVENT" in res_str):
                logger.error("[ERROR] Fallo al adjuntar imagen en DeepSeek: %s", res_str)
                return False
        except Exception as error_adj:
            logger.error("[ERROR] Excepcion al adjuntar imagen en DeepSeek: %s", error_adj)
            return False

        await asyncio.sleep(2.0)

    # Inyección del prompt con React setter
    js_inyeccion_texto = f"""
    (() => {{
        try {{
            const promptText = {json.dumps(prompt)};
            const textarea = document.querySelector('textarea#chat-input, textarea[placeholder*="Mensaje"], textarea[placeholder*="DeepSeek"], textarea.d96f2d2a, textarea._27c9245, textarea[name="search"], textarea');
            if (!textarea) return "NO_TEXTAREA";

            textarea.focus();
            const proto = window.HTMLTextAreaElement.prototype;
            const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
            if (descriptor && descriptor.set) {{
                descriptor.set.call(textarea, promptText);
            }} else {{
                textarea.value = promptText;
            }}

            textarea.dispatchEvent(new InputEvent('input', {{ bubbles: true, cancelable: true }}));
            textarea.dispatchEvent(new Event('change', {{ bubbles: true }}));

            if (!textarea.value || textarea.value.trim().length === 0) {{
                document.execCommand('selectAll', false, null);
                document.execCommand('insertText', false, promptText);
            }}
            return "PROMPT_OK";
        }} catch(e) {{
            return "ERROR: " + e.toString();
        }}
    }})()
    """
    res_texto = await pestana.evaluate(js_inyeccion_texto)
    if isinstance(res_texto, str) and "NO_TEXTAREA" in res_texto:
        logger.error("[ERROR] Textarea de DeepSeek no localizado en el DOM")
        return False

    await asyncio.sleep(0.8)
    await pestana.evaluate(JS_SCROLL_FONDO_DEEPSEEK)

    # Disparo verificado de envío (reintentos hasta comprobar que textarea quedó vacío)
    js_disparar_envio = """
    (() => {
        const textarea = document.querySelector('textarea#chat-input, textarea[placeholder*="Mensaje"], textarea[placeholder*="DeepSeek"], textarea.d96f2d2a, textarea._27c9245, textarea');
        if (textarea) {
            textarea.focus();
            textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
            textarea.dispatchEvent(new KeyboardEvent('keypress', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
            textarea.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
        }
        const sendBtn = document.querySelector('div[role="button"]._52c986b, .ds-button--primary._52c986b, div[role="button"].bd74640a, div[role="button"].ds-button--primary:not(.ds-button--disabled), div[role="button"]:has(svg)');
        if (sendBtn) {
            sendBtn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
            sendBtn.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true }));
            sendBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            sendBtn.click();
            return true;
        }
        return false;
    })()
    """
    mensaje_enviado = False
    for _ in range(4):
        await pestana.evaluate(js_disparar_envio)
        await asyncio.sleep(1.2)
        vacio = await pestana.evaluate("""
        (() => {
            const ta = document.querySelector('textarea#chat-input, textarea[placeholder*="Mensaje"], textarea[placeholder*="DeepSeek"], textarea.d96f2d2a, textarea._27c9245, textarea');
            return !ta || ta.value.trim().length === 0;
        })()
        """)
        if vacio:
            mensaje_enviado = True
            break

    await pestana.evaluate(JS_SCROLL_FONDO_DEEPSEEK)
    if not mensaje_enviado:
        logger.error("[ERROR] No se pudo enviar el mensaje a DeepSeek: el textarea sigue lleno.")
        return False
    return True


async def esperar_respuesta_deepseek(
    pestana: Any,
    tiempo_limite: int = 90,
    intervalo_estabilidad: float = 1.0,
    verificador_cancelacion: Callable[[], bool] | None = None,
) -> str | None:
    """Espera la respuesta final del asistente en DeepSeek con detección de JSON y botones."""
    from procesos_ia.infraestructura.web.base.extractor_json import extraer_y_reparar_json
    js_extract_response = """
    JSON.stringify((() => {
        try {
            const assistantContainers = Array.from(document.querySelectorAll('.ds-assistant-message-main-content, .ds-markdown'));
            if (assistantContainers.length === 0) return { hasAssistantMsg: false, isGenerating: true, hasActionButtons: false, text: "" };
            const latestAssistant = assistantContainers[assistantContainers.length - 1];
            const preElem = latestAssistant.querySelector('.md-code-block pre, pre, code');
            const text = preElem ? (preElem.innerText || "").trim() : (latestAssistant.innerText || "").trim();
            const parent = latestAssistant.closest('._4f9bf79, .ds-message, [data-virtual-list-item-key]') || latestAssistant.parentElement;
            const actionButtons = parent ? parent.querySelectorAll('div[role="button"].db183363, .ds-flex._0a3d93b, div[role="button"]') : [];
            return { hasAssistantMsg: text.length > 5, hasActionButtons: actionButtons.length >= 2, text: text };
        } catch(e) {
            return { hasAssistantMsg: false, error: e.toString(), text: "" };
        }
    })())
    """
    inicio = asyncio.get_event_loop().time()
    ultimo_texto, contador_estable = "", 0

    while (asyncio.get_event_loop().time() - inicio) < tiempo_limite:
        if verificador_cancelacion and verificador_cancelacion():
            return None
        try:
            await pestana.evaluate(JS_SCROLL_FONDO_DEEPSEEK)
            res_val = await pestana.evaluate(js_extract_response)
            if isinstance(res_val, dict):
                info = res_val
            elif res_val and not hasattr(res_val, "exception"):
                info = json.loads(str(res_val))
            else:
                info = {}
        except Exception:
            if verificador_cancelacion and verificador_cancelacion():
                return None
            info = {}

        has_assistant_msg = info.get("hasAssistantMsg", False) or info.get("completo", False) or bool(info.get("texto"))
        has_action_buttons = info.get("hasActionButtons", False)
        raw_text = str(info.get("text") or info.get("texto") or "").strip()

        if not has_assistant_msg or not raw_text:
            for _ in range(max(1, int(intervalo_estabilidad / 0.1))):
                if verificador_cancelacion and verificador_cancelacion():
                    return None
                await asyncio.sleep(0.1)
            continue

        if "{" in raw_text and "}" in raw_text:
            json_parseado = extraer_y_reparar_json(raw_text)
            if isinstance(json_parseado, list) and len(json_parseado) > 0:
                return raw_text
            elif isinstance(json_parseado, dict):
                nombre = str(json_parseado.get("negocio") or json_parseado.get("nombre_negocio") or "").strip()
                if nombre and nombre not in ("Nombre extraído o ND", "Nombre comercial exacto"):
                    return raw_text
                if any(k in json_parseado for k in ("identificador", "habla_espanol", "resultado")):
                    return raw_text
                if info.get("completo") or info.get("es_codigo"):
                    return raw_text

        if len(raw_text) > 10:
            if has_action_buttons or (raw_text == ultimo_texto):
                contador_estable += 1
                if contador_estable >= 2 or has_action_buttons:
                    if "{" in raw_text and "}" in raw_text:
                        json_parseado = extraer_y_reparar_json(raw_text)
                        if json_parseado:
                            return raw_text
                    rescate = extraer_datos_de_texto_plano(raw_text)
                    return json.dumps(rescate)
            else:
                ultimo_texto, contador_estable = raw_text, 0

        for _ in range(max(1, int(intervalo_estabilidad / 0.1))):
            if verificador_cancelacion and verificador_cancelacion():
                return None
            await asyncio.sleep(0.1)

    if ultimo_texto:
        return ultimo_texto if "{" in ultimo_texto else json.dumps(extraer_datos_de_texto_plano(ultimo_texto))
    return None
