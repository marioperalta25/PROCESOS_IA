"""Manipulador DOM para Modo IA de Google Search (SGE / Gemini en Buscador)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from procesos_ia.infraestructura.web.base.extractor_json import extraer_y_reparar_json

logger = logging.getLogger(__name__)

SELECTORES_ACTIVACION = ("button.plR5qb", "button[jsname='B6rgad']", "#composeButton")
SELECTORES_INPUT = ("textarea.ITIRGe", "textarea[aria-label*='pregunta']", "textarea.gLFyf", "textarea")
SELECTORES_SUBMIT = ("button[aria-label*='Enviar']", "button.wdK4Nc", "button[jsname='B6rgad']")


async def activar_modo_ia(pestana: Any) -> bool:
    """Activa el Modo IA de forma instantanea mediante evaluacion DOM unificada."""
    js_activacion = """
    (() => {
        const sels = ["button.plR5qb", "button[jsname='B6rgad']", "#composeButton", "cr-button#composeButton", "cr-button[aria-label*='Modo IA']"];
        for (const s of sels) {
            const el = document.querySelector(s);
            if (el && el.offsetParent !== null) { (el.closest("button, a, div[role='button']") || el).click(); return true; }
        }
        for (const b of Array.from(document.querySelectorAll("button, a, div[role='button'], span"))) {
            const txt = (b.innerText || b.textContent || "").trim();
            const aria = (b.getAttribute("aria-label") || "").trim();
            if (/^Modo\\s*IA/i.test(txt) || /^Modo\\s*IA/i.test(aria) || /AI\\s*Mode/i.test(txt)) {
                (b.closest("button, a, div[role='button']") || b).click(); return true;
            }
        }
        return false;
    })()
    """
    try:
        if bool(await pestana.evaluate(js_activacion)):
            await asyncio.sleep(0.3)
            return True
    except Exception:
        pass
    return False


async def pegar_texto_en_elemento(pestana: Any, elem_input: Any, texto: str) -> bool:
    """Inserta texto completo de forma instantanea sin truncamiento ni tipeo lento."""
    script_js = f"""
    ((elem) => {{
        try {{
            elem.removeAttribute('maxlength');
            elem.maxLength = 100000;
            elem.focus();
            const proto = window.HTMLTextAreaElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
            const textoVal = {json.dumps(texto)};
            if (setter) {{
                setter.call(elem, textoVal);
            }} else {{
                elem.value = textoVal;
            }}
            elem.dispatchEvent(new Event('input', {{ bubbles: true, composed: true }}));
            elem.dispatchEvent(new Event('change', {{ bubbles: true, composed: true }}));
            return elem.value.length;
        }} catch (e) {{
            return -1;
        }}
    }})
    """
    try:
        longitud_inyectada = await elem_input.apply(script_js)
        if longitud_inyectada == len(texto):
            await asyncio.sleep(0.1)
            return True
    except Exception as error_dom:
        logger.debug("[DEBUG] Fallback CDP tras inyeccion directa: %s", error_dom)

    try:
        await elem_input.apply("(elem) => { elem.removeAttribute('maxlength'); elem.maxLength = 100000; elem.focus(); elem.select && elem.select(); }")
        import nodriver.cdp.input_ as cdp_input
        await pestana.send(cdp_input.insert_text(text=texto))
        await asyncio.sleep(0.1)
        return True
    except Exception as error_cdp:
        logger.error("[ERROR] Fallo al insertar texto en textarea: %s", error_cdp)
        return False


async def esperar_input_modo_ia(pestana: Any, timeout_segundos: float = 15.0) -> Any | None:
    """Espera reactivamente a que el input este montado y visible en el DOM."""
    inicio = asyncio.get_event_loop().time()
    js_busca = """
    (() => {
        const sels = [
            "textarea.ITIRGe", "textarea[aria-label*='pregunta']", "textarea.gLFyf",
            "textarea#ti6dpd", "textarea[name='q']", "textarea#input", "textarea"
        ];
        for (const s of sels) {
            const el = document.querySelector(s);
            if (el && (el.offsetWidth > 0 || el.offsetHeight > 0 || el.getClientRects().length > 0)) {
                return s;
            }
        }
        return null;
    })()
    """
    while (asyncio.get_event_loop().time() - inicio) < timeout_segundos:
        try:
            sel = await pestana.evaluate(js_busca)
            if sel:
                elem = await pestana.select(str(sel), timeout=0.8)
                if elem is not None:
                    return elem
        except Exception:
            pass

        try:
            await activar_modo_ia(pestana)
        except Exception:
            pass

        await asyncio.sleep(0.15)
    return None


async def enviar_prompt_modo_ia(pestana: Any, prompt: str, timeout_input: float = 15.0) -> bool:
    """Introduce texto en el input con espera inteligente y despacha el envio."""
    elem_input = await esperar_input_modo_ia(pestana, timeout_segundos=timeout_input)
    if elem_input is None:
        logger.warning("[ALERTA] No se encontro campo de entrada en Modo IA tras esperar")
        return False

    pegado_exitoso = await pegar_texto_en_elemento(pestana, elem_input, prompt)
    if not pegado_exitoso:
        return False

    js_submit = """
    (() => {
        // 1. Boton Modo IA en pantalla inicial
        for (const b of Array.from(document.querySelectorAll("button, div[role='button'], a"))) {
            const txt = (b.innerText || b.textContent || "").trim();
            const aria = (b.getAttribute("aria-label") || "").trim();
            if ((/^Modo\\s*IA/i.test(txt) || /^Modo\\s*IA/i.test(aria) || /AI\\s*Mode/i.test(txt)) && (b.offsetWidth > 0)) {
                (b.closest("button, div[role='button']") || b).click(); return true;
            }
        }
        // 2. Boton de envio dentro de la caja del textarea (descartando + y microfono)
        const ta = document.querySelector("textarea.ITIRGe, textarea[name='q'], textarea");
        const cont = ta ? (ta.closest("form") || ta.closest("[jsmodel]") || ta.closest(".RNNXgb, .a4bIc, .SDkEP") || ta.parentElement?.parentElement) : null;
        if (cont) {
            const btns = Array.from(cont.querySelectorAll("button, div[role='button']"));
            for (const b of btns) {
                const a = (b.getAttribute("aria-label") || "").toLowerCase();
                const t = (b.innerText || b.textContent || "").trim();
                const ignorar = t === "+" || a.includes("voz") || a.includes("voice") || a.includes("micro") || a.includes("config");
                if (!ignorar && (b.offsetWidth > 0 || b.offsetHeight > 0)) {
                    b.click(); return true;
                }
            }
        }
        // 3. Selectores de envio globales
        for (const s of ["button[aria-label*='Enviar']", "button[aria-label*='Send']", "button[data-xid*='send']", "button.wdK4Nc"]) {
            const el = document.querySelector(s);
            if (el && (el.offsetWidth > 0 || el.offsetHeight > 0)) { el.click(); return true; }
        }
        return false;
    })()
    """
    inicio_btn = asyncio.get_event_loop().time()
    clicado = False
    while (asyncio.get_event_loop().time() - inicio_btn) < 3.0:
        try:
            if bool(await pestana.evaluate(js_submit)):
                clicado = True
                await asyncio.sleep(0.3)
                break
        except Exception:
            pass
        await asyncio.sleep(0.15)

    try:
        import nodriver.cdp.input_ as cdp_in
        await pestana.send(cdp_in.dispatch_key_event(type_="keyDown", key="Enter", code="Enter", windows_virtual_key_code=13))
        await pestana.send(cdp_in.dispatch_key_event(type_="keyUp", key="Enter", code="Enter", windows_virtual_key_code=13))
    except Exception:
        pass
    await asyncio.sleep(0.3)
    return True


async def contar_turnos_modo_ia(pestana: Any) -> int:
    """Retorna la cantidad de turnos conversacionales existentes en el DOM."""
    try:
        js = "() => document.querySelectorAll(\"[data-scope-id='turn']\").length"
        res = await pestana.evaluate(js)
        return int(res) if res is not None else 0
    except Exception:
        return 0


async def marcar_turnos_previos_modo_ia(pestana: Any) -> int:
    """Marca en el DOM los elementos existentes para vigilar solo la nueva respuesta."""
    try:
        js = """
        (() => {
            const items = document.querySelectorAll("[data-scope-id='turn'], .n6owBd, .CKgc1d, .mZJni, [data-subtree='aimfl']");
            items.forEach(el => el.setAttribute("data-procesos-ia-visto", "true"));
            return document.querySelectorAll("[data-scope-id='turn']").length;
        })()
        """
        res = await pestana.evaluate(js)
        return int(res) if res is not None else 0
    except Exception:
        return 0


async def esperar_respuesta_modo_ia(
    pestana: Any, timeout_segundos: int = 45, turnos_previos: int = 0, filas_esperadas: int = 0
) -> str:
    """Vigila el DOM y detecta en milisegundos la nueva respuesta completada de la IA."""
    inicio = asyncio.get_event_loop().time()
    ultimo_texto = ""
    estable_ticks = 0

    js_extractor = """
    (() => {
        const tn = Array.from(document.querySelectorAll("[data-scope-id='turn']:not([data-procesos-ia-visto='true']), .CKgc1d:not([data-procesos-ia-visto='true'])"));
        let target = tn.length > 0 ? tn[tn.length - 1] : null;
        if (!target) {
            const bn = Array.from(document.querySelectorAll(".n6owBd:not([data-procesos-ia-visto='true']), [data-subtree='aimfl']:not([data-procesos-ia-visto='true'])"));
            if (bn.length > 0) target = bn[bn.length - 1];
        }
        if (!target) return JSON.stringify({ completo: false, texto: "", lineas: 0 });

        const bloques = Array.from(target.querySelectorAll(".n6owBd, [data-subtree='aimfl']"));
        let texto = bloques.length > 0 ? bloques.map(b => (b.innerText || "").trim()).filter(Boolean).join("\\n") : "";
        if (!texto) {
            const main = target.querySelector("div[data-container-id='main-col'], .mZJni") || target;
            texto = (main.innerText || "").trim();
        }
        if (!texto) {
            return JSON.stringify({ completo: false, texto: "", lineas: 0 });
        }

        const tieneComplete = target.getAttribute("data-complete") === "true" || !!target.querySelector("[data-complete='true']");
        const tieneCopiar = !!target.querySelector("button[aria-label*='Copiar'], button.bKxaof, button[aria-label*='Copy']");
        const tieneCompartir = !!target.querySelector("button[aria-label*='Compartir'], button.eGAasd, button[aria-label*='Share']");
        const cargando = !!document.querySelector(".p8h7ae, .k7bQcd, [role='progressbar']");

        const completo = (tieneComplete || tieneCopiar || tieneCompartir) && !cargando;
        const lineas = texto.split('\\n').map(l => l.trim()).filter(Boolean);

        return JSON.stringify({ completo: completo, texto: texto, lineas: lineas.length });
    })()
    """

    while (asyncio.get_event_loop().time() - inicio) < timeout_segundos:
        try:
            eval_res = await pestana.evaluate(js_extractor)
            if isinstance(eval_res, str) and eval_res.startswith("{"):
                try:
                    estado = json.loads(eval_res)
                except Exception:
                    estado = {}
            else:
                estado = eval_res if isinstance(eval_res, dict) else {}

            completo = estado.get("completo", False)
            texto = (estado.get("texto") or "").strip()
            num_lineas = int(estado.get("lineas", 0))

            if completo and len(texto) > 10:
                if filas_esperadas == 0 or num_lineas >= filas_esperadas:
                    return texto
                estable_ticks += 1
                if estable_ticks >= 4:
                    return texto
            elif filas_esperadas > 0 and num_lineas >= filas_esperadas:
                return texto
            elif len(texto) > 15:
                if texto == ultimo_texto:
                    estable_ticks += 1
                    umbral = 4 if filas_esperadas == 0 else 15
                    if estable_ticks >= umbral:
                        return texto
                else:
                    estable_ticks = 0
                    ultimo_texto = texto
        except Exception:
            pass
        await asyncio.sleep(0.15)

    return ultimo_texto


def extraer_datos_estructurados_modo_ia(texto_respuesta: str) -> dict[str, Any] | list[Any]:
    """Extrae y repara bloques JSON generados por Modo IA si estan presentes."""
    return extraer_y_reparar_json(texto_respuesta)
