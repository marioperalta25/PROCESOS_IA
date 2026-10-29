"""Modulo de dominio para extraccion y estructuracion semantica de fichas de Google Lens."""

from __future__ import annotations

import re
from typing import Any
from bs4 import BeautifulSoup

from procesos_ia.dominio.ia_web.extractor_semantico_lens import (
    extraer_datos_semanticos_lineas,
    inferir_nombre_desde_dominio,
)
from procesos_ia.dominio.ia_web.ficha_negocio import FichaNegocioLens

RE_ESTRUCTURADO = {
    "negocio": re.compile(
        r"(?:^|[\n\r]|[\-\*\u2022]\s*)(?:(?:(?:sitio\s+web\s+(?:oficial\s+)?de\s+la\s+)?(?:el\s+|la\s+)?(?:Nombre\s+(?:del?|de\s+la)\s+)?)?(?:negocio|empresa|compañía|compania)(?:\s+de\s+[^.\n\r:]{1,35})?|Nombre\s+comercial|Company\s+name|Business\s+name)[^\S\r\n]*[:\-][^\S\r\n]*([^\n\r]+)",
        re.IGNORECASE,
    ),
    "licencia": re.compile(
        r"(?:(?:\bmostrando\s+el\s+)?n[uú]mero\s+de\s+licencia\s*[:\-]?|\b(?:Licencia|License|Lic\b\.?|Reg\b\.?)\s*[:\-#]?)\s*([#]?\s*[A-Za-z0-9\-/]{3,})",
        re.IGNORECASE,
    ),
    "propietario": re.compile(
        r"(?:^|[\n\r]|[\-\*\u2022]\s*)(?:(?:\bRepresentante|\bEjecutivo)(?:\s*/\s*(?:Representante|Ejecutivo))?(?:\s+de\s+ventas)?|Contacto|Propietario|Dueño|Dueno|Owner|Agente|Vendedor|Nombre(?!\s+de\s+la\s+empresa|\s+del\s+negocio|\s+comercial))[^\S\r\n]*[:\-][^\S\r\n]*([^\n\r]+)",
        re.IGNORECASE,
    ),
    "telefono": re.compile(
        r"(?:Tel[eé]fonos?(?:\s+(?:de\s+contacto|adicional|principal|alternativo|secundario))?|Phones?|Celular(?:es)?(?:\s+(?:de\s+contacto|adicional|principal|alternativo|secundario))?|Additional phone|Mobile|Contact number)[^\S\r\n]*[:\-]?\s*([^\n\r]+)",
        re.IGNORECASE,
    ),
    "correo": re.compile(r"(?:Correo\s*(?:electr[oó]nico)?|Email|E-mail|Mail)[^\S\r\n]*[:\-]?\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,6}\b)", re.IGNORECASE),
    "sitio_web": re.compile(r"(?:Sitio\s*web|Website|Web|URL)[^\S\r\n]*[:\-]?\s*([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}(?:/[^\s\n\r]*)?)", re.IGNORECASE),
    "ubicacion": re.compile(
        r"(?:Ubicaci[oó]n\s*(?:referencial|principal)?\s*(?:del\s*negocio)?|[AÁ]reas?\s*(?:de\s+servicio|principal|de\s+cobertura)?|Direcci[oó]n|Location|Address)[^\S\r\n]*[:\-][^\S\r\n]*([^\n\r]+)",
        re.IGNORECASE,
    ),
    "categoria": re.compile(
        r"(?:Categoría|Categoria|Rubro|Actividad|Servicios?\s+principales?|Servicios?\s+ofrecidos?|Category|Especialidad(?:es)?)[^\S\r\n]*[:\-][^\S\r\n]*([^\n\r]+)",
        re.IGNORECASE,
    ),
    "idiomas": re.compile(r"(?:Idiomas?|Languages?)[^\S\r\n]*[:\-]?\s*([^\n\r]+)", re.IGNORECASE),
}

PALABRAS_EMPRESA = (
    "llc", "inc", "corp", "co", "ltd", "contractor", "contractors", "roofing", "services", "service",
    "landscaping", "remodeling", "construction", "company", "plumbing", "electric", "painting", "builders", "lawn",
)
RE_PROPIETARIO_ALT = re.compile(
    r"(?i:cuyo\s+propietario\s+es|propiedad\s+de|pertenece a|propietario(?: de)?|due[nñ]o(?: de)?|owner|contact name|persona de contacto|atendido por|a cargo de)\s*[:\-]?\s*([A-Z\u00c0-\u017e][a-z\u00e0-\u017e]+(?:\s+[A-Z\u00c0-\u017e][a-z\u00e0-\u017e]+){1,2})|\b([A-Z\u00c0-\u017e][a-z\u00e0-\u017e]+(?:\s+[A-Z\u00c0-\u017e][a-z\u00e0-\u017e]+){1,2}),\s*(?i:propietario|due[nñ]o|owner)"
)
RE_NEGOCIO_ALT = re.compile(
    r"(?:(?:denominad[oa]|llamado|llamada|de\s+nombre|propietario\s+de|due[nñ]o\s+de|owner\s+of)\s+|pertenece\s+a\s+(?:la\s+empresa|el\s+negocio)(?:\s+de\s+[a-z\u00e0-\u017e]+)?\s+|(?:el\s+logotipo\s+de\s+la\s+imagen\s+corresponde\s+a|el\s+logotipo\s+(?:pertenece\s+a|corresponde\s+a|de)|tarjeta\s+de\s+presentaci[oó]n\s+(?:pertenece\s+a|corresponde\s+a|de)|la\s+imagen\s+muestra\s+(?:un\s+anuncio\s+publicitario\s+de\s+(?:la\s+empresa\s+)?|un\s+logotipo\s+publicitario\s+de\s+|una\s+tarjeta\s+de\s+presentaci[oó]n\s+de\s+)?|informaci[oó]n\s+de\s+contacto\s+de|logo\s+de)\s*)([A-Z0-9\u00c0-\u017e][A-Za-z0-9\u00c0-\u017e\s&\'./\-]+?)(?=[,.\n\r]|(?:\s*\()|\s+(?:un[a]?\s+empresa|un[a]?\s+negocio|dedicad|cuyo|propietario|enfocado|que\s+ofrece)|$)",
    re.IGNORECASE,
)
RE_NEGOCIO = re.compile(
    r"(?:(?:propietario\s+de|due[nñ]o\s+de|owner\s+of|company\s+name\s+is)\s*[:\-]?\s*|nombre\s+comercial\s*[:\-]\s*|(?:(?:sitio\s+web\s+(?:oficial\s+)?de\s+la\s+)?(?:el\s+|la\s+)?(?:Nombre\s+(?:del?|de\s+la)\s+)?)?(?:empresa|negocio|compañía|compania)(?:\s+de\s+[^\n\r:]+)?\s*[:\-]\s*)([^,.\n\r]+)",
    re.IGNORECASE,
)
RE_ACTIVIDAD_LIMPIA = re.compile(
    r"(?i:(?:un|la|el|una)\s+(?:negocio|empresa)\s+de|dedicad[oa]\s+a|especialistas\s+en)\s+([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)*)"
)
RE_ACTIVIDAD_GENERAL = re.compile(
    r"(?:un negocio de|una empresa de|dedicada? a|servicios de|we do all type of|especialistas en|servicios\s+profesionales\s+de|enfocado\s+en\s+la)\s*([^,.\n]+)",
    re.IGNORECASE,
)
RE_TELEFONO_ESTRICTO = re.compile(
    r"(?:(?:\+?1|\b1)[-.\s]*)?\(?([2-9]\d{2})\)?[-.\s]*(\d{3})[-.\s]*(\d{4})\b"
)
RE_UBICACION = re.compile(
    r"(?:\bubicad[oa]s?\s+en|\ben)\s+([A-Z\u00c0-\u017e][a-zA-Z\s]{1,30},\s*[A-Z\u00c0-\u017e][a-zA-Z\s]{1,30}(?:\s+\d{5})?)",
    re.IGNORECASE,
)
RE_CORREO_GENERAL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,6}\b")
RE_SEPARADOR_CAMPOS = re.compile(
    r"(?:\s*|([a-zA-Z0-9\):.+]))(?=(?:(?<!\bde )(?<!\bla )(?:Nombre\s+(?:del?|de\s+la)\s+(?:negocio|empresa|compañía|compania)(?:\s+de\s+[^\n\r:]+)?|Nombre(?:\s+comercial)?|Empresa(?:\s+de\s+[^\n\r:]+)?|Compañía|Compania|Licencia|N[uú]mero\s+de\s+licencia|(?:\bRepresentante|\bEjecutivo)(?:\s*/\s*(?:Representante|Ejecutivo))?(?:\s+de\s+ventas)?|Tel[eé]fonos?(?:\s+(?:de\s+contacto|principal|adicional|secundario|alternativo))?|Celular(?:es)?(?:\s+(?:de\s+contacto|principal|adicional|secundario|alternativo))?|Contacto|Propietarios?|Dueño|Dueno|Owner|Correo(?:\s+electr[oó]nico)?|Email|[AÁ]reas?\s+(?:de\s+servicio|principal|de\s+cobertura)?|Servicios?(?:\s+(?:principal(?:es)?|ofrecidos?))?|Especialidad(?:es)?|Oferta|Ubicaci[oó]n(?:\s+principal|\s+referencial)?|Direcci[oó]n|Sitio\s*web|Idiomas?|Languages?)\s*[:\-]|(?<!/)(?<!\.)(?<!:)(?<!@)\b(?:Facebook|Instagram|TikTok|Google Play|LinkedIn|YouTube|Pinterest|HomeAdvisor|Thumbtack|MapQuest|Nextdoor|Yelp)|¿))",
    re.IGNORECASE,
)


def extraer_datos_html(html: str) -> tuple[str, list[str]]:
    """Usa BeautifulSoup para aislar texto limpio y enlaces de Google Lens."""
    if not html:
        return "", []
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.select("script, style, svg, noscript, .LNSaYe, div[data-sn-container], .NyIrK, div.iaqvce, div[jsname='r5xl4'], button"):
            tag.decompose()
        enlaces: list[str] = []
        for a in soup.find_all("a", href=True):
            href = str(a["href"]).strip()
            if href.startswith("http") and not any(x in href for x in ("google.com", "policies.google.com")):
                if href not in enlaces:
                    enlaces.append(href)
        cont = soup.select_one(".mZJni.Dn7Fzd, div[data-subtree='aimc'], .n6owBd, div[data-container-id='main-col'], div[jsname='KFl8ub']")
        if not cont:
            cont = soup.select_one("div[data-attrid='wa:/description'], .EyBRub") or soup
        lineas: list[str] = []
        desc_div = cont.select_one(".n6owBd, .awi2gc, div[data-attrid='wa:/description']")
        if desc_div:
            desc_cl = BeautifulSoup(str(desc_div), "html.parser")
            for sub in desc_cl(["ul", "ol", "table"]):
                sub.decompose()
            t_desc = desc_cl.get_text(separator=" ", strip=True)
            if t_desc and len(t_desc) > 5 and t_desc not in lineas:
                lineas.append(t_desc)
        for tr in cont.find_all("tr"):
            cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if len(cols) >= 2 and cols[0] and cols[1]:
                lineas.append(f"• {cols[0]}: {cols[1]}")
        for el in cont.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
            t = el.get_text(separator=" ", strip=True)
            if t and len(t) > 3 and t not in lineas:
                lineas.append(f"• {t}" if el.name == "li" else t)
        if not lineas:
            lineas = [l.strip() for l in cont.get_text(separator="\n").splitlines() if l.strip()]
        return "\n".join(lineas), enlaces
    except Exception:
        return "", []


def parsear_sintesis_negocio(
    texto: str = "",
    enlaces: list[str] | None = None,
    id_registro: str = "",
    fuente_imagen: str = "",
    html: str = "",
) -> FichaNegocioLens:
    """Extrae entidades estructuradas priorizando el texto plano sintetizado de la IA."""
    if isinstance(enlaces, str):
        html, enlaces = enlaces, None
    enlaces_res = list(enlaces or [])
    txt_html, enl_html = extraer_datos_html(html)
    for e in enl_html:
        if e not in enlaces_res: enlaces_res.append(e)

    if texto and texto.strip():
        texto_total = texto.strip() + ("\n" + txt_html.strip() if txt_html and txt_html.strip() else "")
    elif txt_html and txt_html.strip():
        texto_total = txt_html.strip()
    else:
        return FichaNegocioLens(id_registro=id_registro, fuente_imagen=fuente_imagen, enlaces=enlaces_res)

    texto_total = re.sub(r"[\u2022\u25e6\u2219]\s*", "\n• ", texto_total)
    texto_total = RE_SEPARADOR_CAMPOS.sub(lambda m: (m.group(1) or "") + "\n", texto_total)

    datos_sem, enl_sem = extraer_datos_semanticos_lineas(texto_total.splitlines())
    for e in enl_sem:
        if e not in enlaces_res: enlaces_res.append(e)

    # Licencia
    licencia = datos_sem.get("licencia", "")
    if not licencia:
        m_lic = RE_ESTRUCTURADO["licencia"].search(texto_total)
        licencia = m_lic.group(1).strip() if m_lic else ""
    if licencia:
        licencia = re.split(r"\s*(?:\b(?:Facebook|Instagram|TikTok|Google Play|LinkedIn|YouTube|Pinterest|HomeAdvisor|Thumbtack|Yelp|MapQuest|Nextdoor)|¿|\bwww\.|\bhttp|\))", licencia, flags=re.IGNORECASE)[0].strip()
        if len(licencia) < 3 or licencia.lower() in ("i", "ion", "no", "na", "n/a", "yes"): licencia = ""

    # 1. Propietario / Contacto
    negocio = ""
    propietario = datos_sem.get("propietario", "")
    if not propietario:
        m_prop = RE_ESTRUCTURADO["propietario"].search(texto_total) or RE_PROPIETARIO_ALT.search(texto_total)
        if m_prop:
            cand = (m_prop.group(1) or m_prop.group(2) or "").strip()
            cand = re.sub(r"\([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\)", "", cand).strip()
            if cand.lower().startswith("de "): cand = cand[3:].strip()
            if any(w in cand.lower().split() or cand.lower().endswith(" " + w) for w in PALABRAS_EMPRESA):
                negocio = cand
                cand = ""
            prefijos = ("la empresa", "el negocio", "una empresa", "un negocio", "de remodelacion", "servicios", "facebook", "sitio web")
            if cand and not any(cand.lower().startswith(p) for p in prefijos):
                if cand.lower() not in ("star", "facebook", "sitio web", "google"):
                    propietario = cand

    # 2. Negocio
    if not negocio: negocio = datos_sem.get("negocio", "")
    if not negocio:
        m_neg = RE_ESTRUCTURADO["negocio"].search(texto_total)
        if m_neg:
            cand_n = m_neg.group(1).strip()
            if not any(cand_n.lower().startswith(x) for x in ("página de inicio", "pagina de inicio", "sitio web", "propietario", "telefono", "correo")):
                negocio = cand_n
    if not negocio:
        for m_alt in RE_NEGOCIO_ALT.finditer(texto_total):
            cand_alt = m_alt.group(1).strip()
            if any(cand_alt.lower().startswith(x) for x in ("propietario", "telefono", "correo", "informacion", "pagina")):
                continue
            if propietario and cand_alt.lower() == propietario.lower():
                continue
            negocio = cand_alt
            break
    if negocio:
        m_lic_neg = re.search(r"\((?:Licencia|License|Lic\b\.?|Reg\b\.?|N[uú]mero\s+de\s+licencia)\s*[:#]?\s*([#]?[A-Za-z0-9\-/]{3,})\)", negocio, re.I)
        if m_lic_neg:
            if not licencia: licencia = m_lic_neg.group(1).strip()
            negocio = re.sub(r"\s*\([^)]*(?:licencia|lic\.)[^)]*\)", "", negocio, flags=re.I).strip()
        negocio = re.sub(r"\s*\((?:licencia|lic\b\.?|license).*$", "", negocio, flags=re.I).strip()
        negocio = re.sub(
            r"^(?:(?:este\s+es\s+)?(?:el|un)\s+logotipo\s+(?:publicitario\s+)?(?:y\s+la\s+informaci[oó]n\s+de\s+contacto\s+)?(?:de\s+|para\s+)?|(?:la\s+imagen\s+(?:muestra\s+)?(?:un\s+logotipo\s+publicitario\s+de\s+|una\s+tarjeta\s+de\s+presentaci[oó]n\s+de\s+|corresponde\s+a\s+|el\s+logotipo\s+de\s+)?)|la\s+tarjeta\s+de\s+presentaci[oó]n\s+(?:pertenece\s+a\s+|corresponde\s+a\s+|de\s+)|el\s+logotipo\s+(?:pertenece\s+a\s+|corresponde\s+a\s+|de\s+)|informaci[oó]n\s+de\s+contacto\s+de\s+|un\s+logotipo\s+publicitario\s+de\s+|un\s+anuncio\s+publicitario\s+de\s+(?:la\s+empresa\s+)?|corresponde\s+a\s+|(?:la|el|una|un)\s+(?:empresa|negocio)\s+(?:de\s+[a-z\u00e0-\u017e]+\s+)?)\s*",
            "", negocio, flags=re.IGNORECASE,
        ).strip()
        negocio = re.sub(r"\s+(?:Este es|La imagen|Nombre de|El Modo).*$", "", negocio, flags=re.IGNORECASE).strip()
        negocio = re.sub(r"[\u2022\ufffd].*$", "", negocio).strip()
        negocio = re.split(r"\s*(?:\b(?:Facebook|Instagram|TikTok|Google Play|LinkedIn|YouTube|Pinterest|HomeAdvisor|Thumbtack)\b|Telefono:|Sitio web:|Servicio:)", negocio, flags=re.I)[0].strip()
        negocio = re.split(r"(?:[.\n\r]|Informaci[oó]n)", negocio)[0].strip()
        if negocio.lower() in ("compartido", "informacion", "la imagen", "el logotipo"): negocio = ""
    if propietario and any(w in propietario.lower().split() or propietario.lower().endswith(" " + w) for w in PALABRAS_EMPRESA):
        if not negocio: negocio = propietario
        propietario = ""

    # 3. Telefonos (estrictamente 10 digitos formato (XXX) XXX-XXXX)
    tels_encontrados: list[str] = []
    for m_tel in RE_ESTRUCTURADO["telefono"].finditer(texto_total):
        for m in RE_TELEFONO_ESTRICTO.finditer(m_tel.group(1)):
            num = f"({m.group(1)}) {m.group(2)}-{m.group(3)}"
            if num not in tels_encontrados: tels_encontrados.append(num)

    if not tels_encontrados and datos_sem.get("telefono"):
        for m in RE_TELEFONO_ESTRICTO.finditer(datos_sem["telefono"]):
            num = f"({m.group(1)}) {m.group(2)}-{m.group(3)}"
            if num not in tels_encontrados: tels_encontrados.append(num)

    if not tels_encontrados:
        for m in RE_TELEFONO_ESTRICTO.finditer(texto_total):
            inicio = m.start()
            prefijo = texto_total[max(0, inicio - 20):inicio].lower()
            if any(descarte in prefijo for descarte in ("stock", "foto", "photo", "id ", "id:", "ref", "código", "codigo")):
                continue
            num = f"({m.group(1)}) {m.group(2)}-{m.group(3)}"
            if num not in tels_encontrados: tels_encontrados.append(num)

    telefono = " / ".join(tels_encontrados)

    # 4. Correo electronico
    correo = datos_sem.get("correo", "")
    if not correo:
        m_cor = RE_ESTRUCTURADO["correo"].search(texto_total) or RE_CORREO_GENERAL.search(texto_total)
        correo = m_cor.group(1).strip() if m_cor else ""

    # 5. Sitio web
    sitio_web = datos_sem.get("sitio_web", "")
    if not sitio_web:
        m_web = RE_ESTRUCTURADO["sitio_web"].search(texto_total)
        sitio_web = m_web.group(1).strip() if m_web else ""
    if sitio_web:
        sitio_web = re.split(r"\s*(?:Oferta|Servicio|Instagram|Facebook|TikTok|\()", sitio_web, flags=re.I)[0].strip()
        sitio_web = re.sub(r"\s+\b(?:en|de|on|at)\b$", "", sitio_web).strip()
    if (not sitio_web or ("." not in sitio_web and not sitio_web.startswith("http"))) and enlaces_res:
        sitio_web = enlaces_res[0]
    elif sitio_web and sitio_web not in enlaces_res: enlaces_res.insert(0, sitio_web)

    # Fallback final de negocio desde dominio de sitio web o correo
    if not negocio or (propietario and (negocio.lower() == propietario.lower() or negocio.lower().startswith("propietario"))):
        negocio = inferir_nombre_desde_dominio(sitio_web) or inferir_nombre_desde_dominio(correo) or ""

    # 7. Ubicacion
    ubicacion = datos_sem.get("ubicacion", "")
    if not ubicacion:
        m_ubi = RE_ESTRUCTURADO["ubicacion"].search(texto_total) or RE_UBICACION.search(texto_total)
        ubicacion = m_ubi.group(1).strip() if m_ubi else ""
    if ubicacion:
        ubicacion = re.split(r"(?:\.\s+(?:La\s+imagen|El\s+Modo|Este\s+es|Informaci[oó]n)|[\n\r]|(?<=\s)La\s+imagen|(?<=\s)El\s+Modo|(?<=\s)Este\s+es|Informaci[oó]n)", ubicacion, flags=re.I)[0].strip()
        ubicacion = re.split(r"\s*(?:\b(?:Facebook|Instagram|TikTok|Google Play|LinkedIn|YouTube|Pinterest|HomeAdvisor|Thumbtack|Yelp|MapQuest|Nextdoor)|¿|\bwww\.|\bhttp)", ubicacion, flags=re.IGNORECASE)[0].strip()
    if ubicacion and any(x in ubicacion.lower() for x in ("exacta", "esta compañia", "esta compania", "?", "deseas", "ayude", "otra zona", "dime", "ciudad o region", "particular", "opciones", "interesa")):
        ubicacion = ""

    # 8. Categoria / Actividad
    m_cat_limp = RE_ACTIVIDAD_LIMPIA.search(texto_total)
    categoria = m_cat_limp.group(1).strip() if m_cat_limp else ""
    if not categoria: categoria = datos_sem.get("categoria", "")
    if not categoria:
        m_cat = RE_ESTRUCTURADO["categoria"].search(texto_total) or RE_ACTIVIDAD_GENERAL.search(texto_total)
        categoria = m_cat.group(1).strip() if m_cat else ""
    if categoria and propietario and (categoria.lower() == propietario.lower() or "operador" in categoria.lower()):
        m_cat_alt = RE_ACTIVIDAD_LIMPIA.search(texto_total) or RE_ACTIVIDAD_GENERAL.search(texto_total)
        categoria = m_cat_alt.group(1).strip() if m_cat_alt else ""
    while re.search(r"\s+(?:en|de|para|con|ubicad[oa]s?|a cargo(?:\s+de)?|denominad[oa]|llamado|llamada)$", categoria, flags=re.IGNORECASE):
        categoria = re.sub(r"\s+(?:en|de|para|con|ubicad[oa]s?|a cargo(?:\s+de)?|denominad[oa]|llamado|llamada)$", "", categoria, flags=re.IGNORECASE).strip()
    if categoria:
        categoria = re.split(r"\s*(?:\b(?:Facebook|Instagram|TikTok|Google Play|LinkedIn|YouTube|Pinterest|HomeAdvisor|Thumbtack|Yelp|MapQuest|Nextdoor)|¿|\bwww\.|\bhttp)", categoria, flags=re.IGNORECASE)[0].strip()
    if categoria and any(x in categoria.lower() for x in ("telefono:", "sitio web:", "correo:", "empresa:", "licencia:")):
        m_act = re.search(r'(?:servicios\s+(?:profesionales\s+)?de|enfocado\s+en\s+la|ofrece\s+servicios\s+de)\s*([^,.\n\r]+)', texto_total, re.I)
        categoria = m_act.group(1).strip() if m_act else ""

    # 9. Idiomas
    m_idi = RE_ESTRUCTURADO["idiomas"].search(texto_total)
    idiomas = datos_sem.get("idiomas", "") or (m_idi.group(1).strip() if m_idi else "")
    if idiomas:
        idiomas = re.split(r"\s*(?:\b(?:Facebook|Instagram|TikTok|Google Play|LinkedIn|YouTube|Pinterest|HomeAdvisor|Thumbtack|Yelp|MapQuest|Nextdoor)|¿)", idiomas, flags=re.IGNORECASE)[0].strip()

    return FichaNegocioLens(
        id_registro=id_registro, propietario=propietario, negocio=negocio,
        categoria=categoria, telefono=telefono, ubicacion=ubicacion, licencia=licencia,
        correo_electronico=correo, sitio_web=sitio_web, idiomas=idiomas,
        enlaces=enlaces_res, texto_sintesis=texto_total.strip(), fuente_imagen=fuente_imagen,
    ).normalizar()
