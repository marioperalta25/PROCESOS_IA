"""Manipulador DOM para DeepSeek Web (https://chat.deepseek.com/)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path
import re
from typing import Any

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


async def enviar_prompt_deepseek(
    pestana: Any,
    prompt: str,
    ruta_imagen: Path | None = None,
) -> bool:
    """Inyecta prompt e imagen con bypass de React y verifica el envío en DeepSeek."""
    base64_data = ""
    nombre_archivo = "imagen.jpg"
    if ruta_imagen and ruta_imagen.exists():
        nombre_archivo = ruta_imagen.name
        with open(ruta_imagen, "rb") as archivo:
            b64_str = base64.b64encode(archivo.read()).decode("utf-8")
            base64_data = f"data:image/jpeg;base64,{b64_str}"

    if base64_data:
        js_adjuntar_imagen = f"""
        (async () => {{
            try {{
                const base64Data = {json.dumps(base64_data)};
                const fetchRes = await fetch(base64Data);
                const blob = await fetchRes.blob();
                const file = new File([blob], "{nombre_archivo}", {{ type: "image/jpeg" }});

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
                    return "ATTACHED_VIA_PASTE";
                }}
                return "NO_INPUT";
            }} catch(e) {{
                return "ERROR: " + e.toString();
            }}
        }})()
        """
        await pestana.evaluate(js_adjuntar_imagen)
        await asyncio.sleep(2.0)

    # Inyección de texto en el textarea con bypass del setter de React
    js_inyeccion_texto = f"""
    (() => {{
        try {{
            const promptText = {json.dumps(prompt)};
            const textarea = document.querySelector('textarea.d96f2d2a, textarea._27c9245, textarea[placeholder*="DeepSeek"], textarea[name="search"], textarea');
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

    # Disparo de envío y verificación de vaciado
    js_disparar_envio = """
    (() => {
        const textarea = document.querySelector('textarea.d96f2d2a, textarea._27c9245, textarea[placeholder*="DeepSeek"], textarea[name="search"], textarea');
        if (textarea) {
            textarea.focus();
            textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
        }
        const sendBtn = document.querySelector('div[role="button"]._52c986b, .ds-button--primary._52c986b, div[role="button"].bd74640a, div[role="button"].ds-button--primary:not(.ds-button--disabled)');
        if (sendBtn) {
            sendBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            sendBtn.click();
            return true;
        }
        return false;
    })()
    """
    for intento in range(3):
        await pestana.evaluate(js_disparar_envio)
        await asyncio.sleep(1.0)
        # Verificar si el textarea ya no tiene el prompt
        vacio = await pestana.evaluate("""
        (() => {
            const ta = document.querySelector('textarea.d96f2d2a, textarea._27c9245, textarea');
            return !ta || ta.value.trim().length === 0;
        })()
        """)
        if vacio:
            break

    await pestana.evaluate(JS_SCROLL_FONDO_DEEPSEEK)
    return True


async def esperar_respuesta_deepseek(
    pestana: Any,
    tiempo_limite: int = 45,
    intervalo_estabilidad: float = 1.0,
) -> str | None:
    """Espera la respuesta final del asistente en DeepSeek Web."""
    js_obtener_asistente = """
    (() => {
        const msgs = document.querySelectorAll('.ds-assistant-message-main-content, .ds-markdown');
        if (msgs.length === 0) return { texto: "", completo: false };
        const ultimo = msgs[msgs.length - 1];
        const acciones = ultimo.querySelectorAll('div[role="button"].db183363, .ds-flex._0a3d93b');
        return {
            texto: (ultimo.innerText || "").trim(),
            completo: acciones.length >= 2
        };
    })()
    """
    inicio = asyncio.get_event_loop().time()
    ultimo_texto = ""
    contador_estable = 0

    while (asyncio.get_event_loop().time() - inicio) < tiempo_limite:
        await pestana.evaluate(JS_SCROLL_FONDO_DEEPSEEK)
        try:
            info = await pestana.evaluate(js_obtener_asistente)
        except Exception:
            info = None

        if isinstance(info, dict):
            texto_actual = str(info.get("texto", "")).strip()
            completo = bool(info.get("completo", False))

            if texto_actual:
                if (texto_actual == ultimo_texto) or completo:
                    contador_estable += 1
                    if contador_estable >= 2:
                        return texto_actual
                else:
                    ultimo_texto = texto_actual
                    contador_estable = 0

        await asyncio.sleep(intervalo_estabilidad)

    return ultimo_texto if ultimo_texto else None
