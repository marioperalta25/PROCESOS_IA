"""Manipulador DOM para Modo IA de Google Search (SGE / Gemini en Buscador)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from procesos_ia.infraestructura.web.base.extractor_json import extraer_y_reparar_json

logger = logging.getLogger(__name__)

SELECTORES_ACTIVACION = (
    "button.plR5qb", "button[jsname='B6rgad']", "span.lTxWLe", "#composeButton",
    "cr-button#composeButton", "cr-button[aria-label*='Modo IA']", "cr-button.compose-container",
)
SELECTORES_INPUT = (
    "textarea.ITIRGe", "textarea[aria-label*='pregunta']", "textarea[placeholder*='pregunta']",
    "textarea.gLFyf", "textarea#ti6dpd", "textarea[name='q']", "textarea[jsname='yZiJbe']",
    "textarea#input", "#composeboxInput textarea", "#inputWrapper textarea",
)

async def activar_modo_ia(pestana: Any) -> bool:
    """Activa el Modo IA haciendo clic en el boton correspondiente si esta disponible."""
    js = """
    (() => {
        const sels = ["button.plR5qb", "button[jsname='B6rgad']", "#composeButton", "cr-button#composeButton"];
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
        if bool(await pestana.evaluate(js)):
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
            if (setter) {{ setter.call(elem, textoVal); }} else {{ elem.value = textoVal; }}
            elem.dispatchEvent(new Event('input', {{ bubbles: true, composed: true }}));
            elem.dispatchEvent(new Event('change', {{ bubbles: true, composed: true }}));
            return elem.value.length;
        }} catch (e) {{
            return -1;
        }}
    }})
    """
    try:
        if await elem_input.apply(script_js) == len(texto):
            await asyncio.sleep(0.1)
            return True
    except Exception as err:
        logger.debug("[INFO] Fallback CDP tras inyeccion directa: %s", err)

    try:
        await elem_input.apply("(elem) => { elem.removeAttribute('maxlength'); elem.maxLength = 100000; elem.focus(); }")
        import nodriver.cdp.input_ as cdp_input
        await pestana.send(cdp_input.insert_text(text=texto))
        await asyncio.sleep(0.1)
        return True
    except Exception as err:
        logger.error("[ERROR] Fallo al insertar texto en textarea: %s", err)
        return False

async def esperar_input_modo_ia(pestana: Any, timeout_segundos: float = 15.0) -> Any | None:
    """Espera reactivamente a que el input este montado y visible en el DOM."""
    inicio = asyncio.get_event_loop().time()
    js_busca = """
    (() => {
        const sels = ["textarea.ITIRGe", "textarea[aria-label*='pregunta']", "textarea.gLFyf", "textarea#ti6dpd", "textarea[name='q']", "textarea"];
        for (const s of sels) {
            const el = document.querySelector(s);
            if (el && (el.offsetWidth > 0 || el.offsetHeight > 0 || el.getClientRects().length > 0)) return s;
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
        logger.warning("[ALERTA] No se encontro campo de entrada en Modo IA")
        return False
    if not await pegar_texto_en_elemento(pestana, elem_input, prompt):
        return False
    await asyncio.sleep(0.15)
    js_submit = """
    (() => {
        for (const b of Array.from(document.querySelectorAll("button, div[role='button'], a"))) {
            const txt = (b.innerText || b.textContent || "").trim();
            const aria = (b.getAttribute("aria-label") || "").trim();
            if ((/^Modo\\s*IA/i.test(txt) || /^Modo\\s*IA/i.test(aria) || /^AI\\s*Mode/i.test(txt)) && (b.offsetWidth > 0 || b.offsetHeight > 0)) {
                (b.closest("button, div[role='button']") || b).click();
                return "modo_ia_inicial";
            }
        }
        for (const s of ["button[aria-label*='Enviar']", "button[aria-label*='Send']", "button[data-xid*='send']", "button.wdK4Nc", "button[jsname='w019Fc']", "cr-composebox-submit"]) {
            const el = document.querySelector(s);
            if (el && (el.offsetWidth > 0 || el.offsetHeight > 0)) { el.click(); return "selector_submit"; }
        }
        const ta = document.querySelector("textarea.ITIRGe, textarea[name='q'], textarea");
        const cont = ta ? (ta.closest("form") || ta.closest("[jsmodel]") || ta.closest(".RNNXgb, .a4bIc, .SDkEP") || ta.parentElement?.parentElement) : null;
        if (cont) {
            const btns = Array.from(cont.querySelectorAll("button, div[role='button']")).filter(b => b.offsetWidth > 0 || b.offsetHeight > 0);
            for (const b of btns) {
                const a = (b.getAttribute("aria-label") || "").toLowerCase();
                const t = (b.innerText || b.textContent || "").trim().toLowerCase();
                if (t === "+" || a.includes("agregar") || a.includes("add") || a.includes("adjunt") || a.includes("imagen") || a.includes("foto") || a.includes("archivo") || a.includes("voz") || a.includes("micro") || a.includes("config")) continue;
                if (a.includes("enviar") || a.includes("send") || b.getAttribute("type") === "submit") { b.click(); return "boton_contenedor"; }
            }
            const validos = btns.filter(b => {
                const a = (b.getAttribute("aria-label") || "").toLowerCase();
                const t = (b.innerText || b.textContent || "").trim().toLowerCase();
                return t !== "+" && !a.includes("agregar") && !a.includes("adjunt") && !a.includes("voz") && !a.includes("micro");
            });
            if (validos.length > 0) { validos[validos.length - 1].click(); return "ultimo_boton"; }
        }
        return null;
    })()
    """
    try:
        await pestana.evaluate(js_submit)
    except Exception:
        pass
    try:
        await elem_input.apply("(elem) => { elem.focus(); }")
        import nodriver.cdp.input_ as cdp_in
        await pestana.send(cdp_in.dispatch_key_event(type_="keyDown", key="Enter", code="Enter", windows_virtual_key_code=13))
        await pestana.send(cdp_in.dispatch_key_event(type_="keyUp", key="Enter", code="Enter", windows_virtual_key_code=13))
    except Exception:
        try:
            await elem_input.send_keys("\n")
        except Exception:
            pass
    await asyncio.sleep(0.3)
    return True

async def contar_turnos_modo_ia(pestana: Any) -> int:
    """Retorna la cantidad unificada de turnos conversacionales existentes en el DOM."""
    js = """
    (() => {
        const turns = document.querySelectorAll("[data-scope-id='turn']");
        if (turns && turns.length > 0) return turns.length;
        const blocks = document.querySelectorAll("div[data-container-id='main-col'], .n6owBd");
        return blocks ? blocks.length : 0;
    })()
    """
    try:
        res = await pestana.evaluate(js)
        return int(res) if res is not None else 0
    except Exception:
        return 0

async def marcar_turnos_previos_modo_ia(pestana: Any) -> int:
    """Compatibilidad de conteo unificado de turnos para procesamiento de lotes."""
    return await contar_turnos_modo_ia(pestana)

async def esperar_respuesta_modo_ia(
    pestana: Any, timeout_segundos: int = 45, turnos_previos: int = 0, filas_esperadas: int = 0
) -> str:
    """Vigila el DOM de forma reactiva y extrae limpiamente la respuesta con blindaje multicapa."""
    inicio = asyncio.get_event_loop().time()
    ultimo_texto = ""
    ultimo_cambio = inicio

    js_extractor = """
    (() => {
        const turns = document.querySelectorAll("[data-scope-id='turn']");
        const nTurnos = turns ? turns.length : 0;
        const target = nTurnos > 0 ? turns[nTurnos - 1] : document.body;
        if (!target) return JSON.stringify({ num_turnos: 0, completo: false, texto: "", lineas: 0 });

        let aiCont = target.querySelector("[data-subtree='aimc'], div[data-container-id='main-col'], .mZJni");
        if (!aiCont) {
            const copyBtn = target.querySelector("button[aria-label*='Copiar texto'], button[aria-label*='Copy text'], button.bKxaof, button[aria-label*='Respuesta correcta']");
            if (copyBtn) aiCont = copyBtn.closest("[data-sfc-root]") || copyBtn.parentElement?.parentElement;
        }
        if (!aiCont && target.children.length >= 2) {
            const noUser = Array.from(target.children).filter(c => !c.querySelector("button[aria-label*='Editar'], button[aria-label*='Edit']"));
            if (noUser.length > 0) aiCont = noUser[noUser.length - 1];
        }
        if (!aiCont) return JSON.stringify({ num_turnos: nTurnos, completo: false, texto: "", lineas: 0 });

        let blocks = Array.from(aiCont.querySelectorAll(".n6owBd, [data-subtree='aimfl']"));
        if (blocks.length === 0) blocks = [aiCont];

        const lineParts = [];
        blocks.forEach(cb => {
            const clone = cb.cloneNode(true);
            clone.querySelectorAll("h1, h2, h3, button, svg, [role='button'], .vDOt8c, .RkJvxe, .YHsVn, [aria-hidden='true'], [data-key='aimhl']").forEach(e => e.remove());
            clone.querySelectorAll("br").forEach(br => br.replaceWith("\\n"));
            const t = (clone.innerText || clone.textContent || "").trim();
            if (t) lineParts.push(t);
        });
        const txt = lineParts.join("\\n").trim();

        const hasCopy = !!target.querySelector("button.bKxaof, button[aria-label*='Copiar texto'], button[aria-label*='Copy text']");
        const hasShare = !!target.querySelector("button.eGAasd, button[aria-label*='Compartir'], button[aria-label*='Share']");
        const hasThumbs = !!target.querySelector("button.cEme7d, button[aria-label*='Respuesta correcta']");
        const isProgress = !!document.querySelector("div[role='progressbar'], .Hz4U2, .k7bQcd, .p8h7ae");

        const completo = (hasCopy || hasShare || hasThumbs) && !isProgress;
        const lines = txt.split('\\n').map(l => l.trim()).filter(Boolean);
        return JSON.stringify({ num_turnos: nTurnos, completo: completo, texto: txt, lineas: lines.length });
    })()
    """
    while (asyncio.get_event_loop().time() - inicio) < timeout_segundos:
        try:
            eval_res = await pestana.evaluate(js_extractor)
            estado = {}
            if isinstance(eval_res, str):
                try:
                    estado = json.loads(eval_res)
                except Exception:
                    estado = {}
            elif isinstance(eval_res, list):
                estado = {k: (v.get("value") if isinstance(v, dict) and "value" in v else v) for k, v in eval_res if isinstance(k, str)}
            elif isinstance(eval_res, dict):
                estado = eval_res

            n_turnos = int(estado.get("num_turnos", 0))
            completo = bool(estado.get("completo", False))
            texto = (estado.get("texto") or "").strip()
            num_lineas = int(estado.get("lineas", 0))

            if n_turnos > turnos_previos or turnos_previos == 0:
                if completo and len(texto) >= 1:
                    if filas_esperadas == 0 or num_lineas >= filas_esperadas:
                        return texto
                if filas_esperadas > 0 and num_lineas >= filas_esperadas and completo:
                    return texto
                if texto and texto != ultimo_texto:
                    ultimo_texto = texto
                    ultimo_cambio = asyncio.get_event_loop().time()
                elif texto and (asyncio.get_event_loop().time() - ultimo_cambio) >= 1.5:
                    if filas_esperadas == 0 or num_lineas >= filas_esperadas:
                        return texto
        except Exception:
            pass
        await asyncio.sleep(0.15)
    return ultimo_texto

async def extraer_html_ultimo_turno(pestana: Any) -> str:
    """Extrae el HTML crudo del ultimo turno para bitacora de auditoria."""
    js = """
    (() => {
        const turns = document.querySelectorAll("[data-scope-id='turn']");
        const t = (turns && turns.length > 0) ? turns[turns.length - 1] : document.querySelector("div[data-container-id='main-col']");
        return t ? (t.outerHTML || t.innerHTML || "") : "";
    })()
    """
    try:
        res = await pestana.evaluate(js)
        return str(res) if res is not None else ""
    except Exception:
        return ""

def extraer_datos_estructurados_modo_ia(texto_respuesta: str) -> dict[str, Any] | list[Any]:
    """Extrae y repara bloques JSON generados por Modo IA si estan presentes."""
    return extraer_y_reparar_json(texto_respuesta)
