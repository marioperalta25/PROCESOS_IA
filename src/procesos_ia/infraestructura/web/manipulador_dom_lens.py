"""Manipulador DOM especializado para interaccion y extraccion con Google Lens."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any

from procesos_ia.dominio.ficha_negocio import FichaNegocioLens
from procesos_ia.dominio.parseador_ficha_lens import parsear_sintesis_negocio
from procesos_ia.infraestructura.web.selectores_lens import SELECTORES_LENS

logger = logging.getLogger(__name__)

__all__ = [
    "SELECTORES_LENS", "parsear_sintesis_negocio", "abrir_modal_lens",
    "cargar_archivo_en_lens", "cargar_url_en_lens", "esperar_vision_general_ia",
    "extraer_enlaces_relacionados",
]


async def abrir_modal_lens(pestana: Any, selectores: list[str] | None = None) -> bool:
    """Localiza y hace clic en el boton de apertura de Google Lens."""
    for selector in (selectores or SELECTORES_LENS["boton_apertura"]):
        try:
            elem = await pestana.select(selector, timeout=2)
            if elem is not None:
                await elem.click()
                await asyncio.sleep(1.0)
                return True
        except Exception:
            continue
    return False


async def cargar_archivo_en_lens(
    pestana: Any,
    ruta_archivo: Path,
    selectores: dict[str, list[str]] | None = None,
) -> bool:
    """Adjunta un archivo al modal de Google Lens combinando interceptor CDP y Shadow DOM."""
    if not ruta_archivo.is_file():
        logger.warning("[ALERTA] Archivo local para Lens no existe: %s", ruta_archivo)
        return False
    sels = selectores or SELECTORES_LENS
    exito_cdp = False
    try:
        import nodriver.cdp.dom as cdp_dom
        import nodriver.cdp.page as cdp_page

        evento_chooser = asyncio.Event()
        node_id_ref: list[int | None] = [None]

        async def _al_abrir(event: cdp_page.FileChooserOpened) -> None:
            node_id_ref[0] = getattr(event, "backend_node_id", None)
            evento_chooser.set()

        pestana.add_handler(cdp_page.FileChooserOpened, _al_abrir)
        await pestana.send(cdp_page.set_intercept_file_chooser_dialog(enabled=True))
        for sel in sels["disparador_subida"]:
            try:
                el = await pestana.select(sel, timeout=1)
                if el is not None:
                    await el.click()
                    break
            except Exception:
                continue
        try:
            await asyncio.wait_for(evento_chooser.wait(), timeout=2.5)
            if node_id_ref[0] is not None:
                await pestana.send(
                    cdp_dom.set_file_input_files(
                        files=[str(ruta_archivo.resolve())], backend_node_id=node_id_ref[0]
                    )
                )
                exito_cdp = True
        except asyncio.TimeoutError:
            pass
        finally:
            try:
                pestana.remove_handler(cdp_page.FileChooserOpened, _al_abrir)
                await pestana.send(cdp_page.set_intercept_file_chooser_dialog(enabled=False))
            except Exception:
                pass
    except Exception as err:
        logger.debug("[DEBUG] Fallback a inyeccion JS: %s", err)

    if exito_cdp:
        await asyncio.sleep(2.0)
        return True

    try:
        mime, _ = mimetypes.guess_type(str(ruta_archivo))
        with open(ruta_archivo, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        data_uri = f"data:{mime or 'image/jpeg'};base64,{b64}"
        zonas_json = json.dumps(sels["zonas_arrastre"])
        js = f"""
        (async () => {{
            try {{
                const res = await fetch({json.dumps(data_uri)});
                const blob = await res.blob();
                const file = new File([blob], {json.dumps(ruta_archivo.name)}, {{ type: {json.dumps(mime or 'image/jpeg')} }});
                const dt = new DataTransfer();
                dt.items.add(file);
                function buscarShadow(raiz) {{
                    let inp = raiz.querySelector('input[type="file"], input[name="encoded_image"]');
                    if (inp) return inp;
                    for (const h of raiz.querySelectorAll('*')) {{
                        if (h.shadowRoot) {{ const r = buscarShadow(h.shadowRoot); if (r) return r; }}
                    }}
                    return null;
                }}
                const finp = buscarShadow(document);
                if (finp) {{
                    finp.files = dt.files;
                    finp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return "INPUT_OK";
                }}
                let dz = null;
                for (const s of {zonas_json}) {{ dz = document.querySelector(s); if (dz) break; }}
                dz = dz || document.body;
                dz.dispatchEvent(new DragEvent('dragenter', {{ dataTransfer: dt, bubbles: true }}));
                dz.dispatchEvent(new DragEvent('dragover', {{ dataTransfer: dt, bubbles: true }}));
                dz.dispatchEvent(new DragEvent('drop', {{ dataTransfer: dt, bubbles: true }}));
                return "DROP_OK";
            }} catch (e) {{ return "ERR: " + e; }}
        }})();
        """
        await pestana.evaluate(js)
        await asyncio.sleep(2.0)
        return True
    except Exception as error:
        logger.warning("[ALERTA] Fallo al cargar archivo en Lens: %s", error)
        return False


async def cargar_url_en_lens(
    pestana: Any, url_imagen: str, selectores: dict[str, list[str]] | None = None
) -> bool:
    """Pega la URL de imagen en el modal de Lens y ejecuta la busqueda."""
    sels = selectores or SELECTORES_LENS
    try:
        caja_input = None
        for sel in sels["campo_url"]:
            caja_input = await pestana.select(sel, timeout=2)
            if caja_input is not None: break
        if caja_input is None: return False
        await caja_input.send_keys(url_imagen)
        await asyncio.sleep(0.5)

        btn_buscar = None
        for sel in sels["boton_buscar_url"]:
            btn_buscar = await pestana.select(sel, timeout=2)
            if btn_buscar is not None: break
        if btn_buscar is not None:
            await btn_buscar.click()
        else:
            await caja_input.send_keys("\n")
        await asyncio.sleep(2.0)
        return True
    except Exception as error:
        logger.warning("[ALERTA] Fallo al cargar URL en Google Lens: %s", error)
        return False


async def esperar_vision_general_ia(
    pestana: Any, timeout_segundos: int = 40, selectores: dict[str, list[str]] | None = None
) -> tuple[str, str]:
    """Espera la respuesta de IA en Google Lens, detectando el tipo exacto de respuesta."""
    tiempo_inicio = asyncio.get_event_loop().time()
    ultimo_texto = ""
    estable_ticks = 0
    coincidencias_inicio: float | None = None
    js_inspector = """
    (() => {
        const alertBox = document.querySelector('div[jsname="N2QsAf"], div.dEZYP[role="alert"]');
        if (alertBox && alertBox.style.display !== 'none') {
            for (const sp of alertBox.querySelectorAll('span')) {
                if (sp.style.display !== 'none' && sp.innerText && sp.innerText.trim().length > 3) {
                    return JSON.stringify({ tipo: 'ERROR_SUBIDA', texto: sp.innerText.trim() });
                }
            }
        }
        const noDisp = document.querySelector("span[jsname='lGsj1']");
        if (noDisp && noDisp.style.display !== 'none' && noDisp.innerText && noDisp.innerText.trim().length > 0) {
            return JSON.stringify({ tipo: 'SIN_VISION_GENERAL', texto: noDisp.innerText.trim() });
        }
        const ac = document.querySelector('.UUbT9, .aajZCb');
        if (ac && ac.style.display !== 'none') ac.style.display = 'none';

        const candidatos = [
            "div[data-container-id='main-col']", "div[jsname='KFl8ub']",
            ".mZJni.Dn7Fzd", ".n6owBd", "ul.XSq4R", "div[data-subtree='aimc']", ".pWvJNd"
        ];
        let cont = null;
        for (const s of candidatos) {
            const el = document.querySelector(s);
            if (el) {
                const cl = el.cloneNode(true);
                for (const sc of cl.querySelectorAll('script, style')) sc.remove();
                const t = (cl.innerText || '').trim();
                if (t.length > 20 && !t.includes('function(') && !t.includes('window.')) {
                    cont = cl; break;
                }
            }
        }
        if (cont) {
            const txt = cont.innerText.trim();
            if (/No hay una visi[oó]n general|AI Overview isn't available/i.test(txt)) {
                return JSON.stringify({ tipo: 'SIN_VISION_GENERAL', texto: txt });
            }
            const tieneContacto = !!cont.querySelector('ul.XSq4R, li.Z1qcYe') || /Tel[eé]fonos?|Licencia|Correo|Sitio web/i.test(txt);
            return JSON.stringify({ tipo: 'EXITOSO', texto: txt, completo: tieneContacto });
        }
        const visual = document.querySelector('div[jsname="r5xl4"], .Vd9M6, .G19kAf, a.PMDqCb, div.iaqvce');
        if (visual) return JSON.stringify({ tipo: 'VISUAL_PRESENTE', texto: '' });
        return JSON.stringify({ tipo: 'ESPERANDO', texto: '' });
    })()
    """
    while (asyncio.get_event_loop().time() - tiempo_inicio) < timeout_segundos:
        try:
            eval_res = await pestana.evaluate(js_inspector)
            if isinstance(eval_res, str) and eval_res.startswith("{"):
                try: eval_res = json.loads(eval_res)
                except Exception: eval_res = None
            elif isinstance(eval_res, list):
                eval_res = dict((k, getattr(v, "value", v)) for k, v in eval_res)
            if isinstance(eval_res, dict):
                tipo = eval_res.get("tipo", "ESPERANDO")
                txt_res = eval_res.get("texto", "")
                if tipo == "ERROR_SUBIDA":
                    return txt_res or "[ERROR] Fallo de subida en Google Lens", "ERROR_SUBIDA"
                if tipo == "SIN_VISION_GENERAL":
                    return txt_res or "[INFO] No hay visión general disponible.", "SIN_VISION_GENERAL"
                if tipo == "EXITOSO":
                    completo = eval_res.get("completo", False)
                    if completo: return txt_res, "EXITOSO"
                    if txt_res == ultimo_texto and len(txt_res) > 20:
                        estable_ticks += 1
                        if estable_ticks >= 3: return txt_res, "EXITOSO"
                    else:
                        estable_ticks = 0
                    ultimo_texto = txt_res
                elif tipo == "VISUAL_PRESENTE":
                    ahora = asyncio.get_event_loop().time()
                    if coincidencias_inicio is None: coincidencias_inicio = ahora
                    elif (ahora - coincidencias_inicio) > 3.5:
                        return "[INFO] Coincidencias visuales presentes.", "SIN_VISION_GENERAL"
        except Exception:
            pass
        await asyncio.sleep(0.4)

    if ultimo_texto:
        return ultimo_texto, "EXITOSO"
    return "[ALERTA] Tiempo agotado sin respuesta del módulo de IA de Lens.", "TIMEOUT_SIN_RESPUESTA"


async def extraer_enlaces_relacionados(
    pestana: Any, selectores: dict[str, list[str]] | None = None
) -> list[str]:
    """Extrae enlaces de fuentes externas citadas en la respuesta de Lens."""
    sels = selectores or SELECTORES_LENS
    js = """
    (() => {
        const links = [];
        for (const a of document.querySelectorAll("a.PMDqCb, .WBgIic a, div.iaqvce a, div.C5trKf a, a.alLuqe")) {
            if (a.href && a.href.startsWith("http") && !a.href.includes("google.com")) {
                if (!links.includes(a.href)) links.push(a.href);
            }
        }
        return JSON.stringify(links);
    })()
    """
    try:
        res = await pestana.evaluate(js)
        if isinstance(res, str) and res.startswith("["): return json.loads(res)
        if isinstance(res, list): return res
    except Exception:
        pass

    enlaces: list[str] = []
    try:
        if hasattr(pestana, "select_all"):
            for sel in sels.get("enlaces_relacionados", []):
                for el in (await pestana.select_all(sel) or []):
                    href = getattr(el, "attrs", {}).get("href") or getattr(el, "href", "")
                    if href and href.startswith("http") and "google.com" not in href:
                        enlaces.append(href)
    except Exception:
        pass
    return list(dict.fromkeys(enlaces))
