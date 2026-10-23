"""Modulo de dominio para extraccion y estructuracion semantica de fichas de Google Lens."""

from __future__ import annotations

import re
from typing import Any
from bs4 import BeautifulSoup

from procesos_ia.dominio.ficha_negocio import FichaNegocioLens

RE_ESTRUCTURADO = {
    "negocio": re.compile(
        r"(?:^|[\n\r]|[\-\*\u2022]\s*)(?:Nombre\s+de\s+la\s+empresa|Nombre(?:\s+comercial)?|Compañía|Compania|Empresa|Negocio|Company name|Business name)[^\S\r\n]*[:\-][^\S\r\n]*([^\n\r]+)",
        re.IGNORECASE,
    ),
    "licencia": re.compile(
        r"(?:N[uú]mero\s+de\s+licencia|Licencia|License|Lic\.?|Reg\.?)[^\S\r\n]*[:\-][^\S\r\n]*([#A-Za-z0-9\-/]+)",
        re.IGNORECASE,
    ),
    "propietario": re.compile(
        r"(?:^|[\n\r]|[\-\*\u2022]\s*)(?:Representante(?:\s+de\s+ventas)?|Contacto|Propietario|Dueño|Dueno|Owner|Ejecutivo\s*(?:de\s*ventas)?|Agente|Vendedor)[^\S\r\n]*[:\-][^\S\r\n]*([^\n\r]+)",
        re.IGNORECASE,
    ),
    "telefono": re.compile(
        r"(?:Tel[eé]fonos?|Phones?|Celulares?|Additional phone|Mobile|Contact number)[^\S\r\n]*[:\-]?\s*([^\n\r]+)",
        re.IGNORECASE,
    ),
    "correo": re.compile(
        r"(?:Correo\s*(?:electr[oó]nico)?|Email|E-mail|Mail)[^\S\r\n]*[:\-]?\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,6}\b)",
        re.IGNORECASE,
    ),
    "sitio_web": re.compile(
        r"(?:Sitio\s*web|Website|Web|URL)[^\S\r\n]*[:\-]?\s*([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}(?:/[^\s\n\r]*)?)",
        re.IGNORECASE,
    ),
    "ubicacion": re.compile(
        r"(?:Ubicaci[oó]n\s*(?:referencial\s*(?:del\s*negocio)?)?|Direcci[oó]n|Location|Address)[^\S\r\n]*[:\-]?\s*([^\n\r]+)",
        re.IGNORECASE,
    ),
    "categoria": re.compile(
        r"(?:Categoría|Categoria|Rubro|Actividad|Servicios?|Category)[^\S\r\n]*[:\-]?\s*([^\n\r]+)",
        re.IGNORECASE,
    ),
    "idiomas": re.compile(
        r"(?:Idiomas?|Languages?)[^\S\r\n]*[:\-]?\s*([^\n\r]+)", re.IGNORECASE
    ),
}

RE_PROPIETARIO_CUYO = re.compile(
    r"(?:cuyo\s+propietario\s+es|propiedad\s+de)\s+([A-Z\u00c0-\u017e][a-z\u00e0-\u017e]+(?:\s+[A-Z\u00c0-\u017e][a-z\u00e0-\u017e]+){1,3})",
    re.IGNORECASE,
)
RE_PROPIETARIO_INVERSO = re.compile(
    r"\b([A-Z\u00c0-\u017e][a-z\u00e0-\u017e]+(?:\s+[A-Z\u00c0-\u017e][a-z\u00e0-\u017e]+){1,3}),\s*(?:propietario|due[nñ]o|owner)",
    re.IGNORECASE,
)
RE_PROPIETARIO = re.compile(
    r"(?:pertenece a|propietario(?: de)?|due[nñ]o(?: de)?|owner|contact name|persona de contacto|atendido por)\s*[:\-]?\s*([A-Z\u00c0-\u017e][a-z\u00e0-\u017e]+(?:\s+[A-Z\u00c0-\u017e][a-z\u00e0-\u017e]+){1,3})",
    re.IGNORECASE,
)
RE_NEGOCIO_LOGOTIPO = re.compile(
    r"(?:el\s+logotipo\s+de|logotipo\s+de|logo\s+de|muestra\s+(?:el\s+logotipo\s+de\s+)?)\s*([A-Z0-9\u00c0-\u017e][A-Za-z0-9\s&\'./\-]+?)(?:,\s*(?:un[a]?\s+empresa|un[a]?\s+negocio|dedicad)|\.|\n|$)",
    re.IGNORECASE,
)
RE_NEGOCIO_CONTACTO = re.compile(
    r"(?:informaci[oó]n\s+de\s+contacto\s+de|tarjeta\s+de\s+presentaci[oó]n\s+de)\s+([A-Z0-9\u00c0-\u017e][A-Za-z0-9\s&\'./\-]+?)(?:,\s*un\s+negocio|,\s*una\s+empresa|,\s*cuyo|,\s*propietario|\.|\n|$)",
    re.IGNORECASE,
)
RE_NEGOCIO_EMPRESA_DE = re.compile(
    r"(?:empresa|negocio)\s+de\s+[a-záéíóúñ]+\s+([A-Z0-9\u00c0-\u017e][A-Za-z0-9\s&\'./\-]+?)(?:,\s*cuyo|,\s*propietario|\.|\n|$)",
    re.IGNORECASE,
)
RE_NEGOCIO_PERTENECE = re.compile(
    r"pertenece\s+a\s+(?:la\s+empresa|el\s+negocio)(?:\s+de\s+[a-z\u00e0-\u017e]+)?\s+([A-Z0-9\u00c0-\u017e][A-Za-z0-9\s&\'./\-]+?)(?:,\s*cuyo|,\s*propietario|\.|\n|$)",
    re.IGNORECASE,
)
RE_NEGOCIO = re.compile(
    r"(?:propietario de|due[nñ]o de|owner of|empresa|negocio|company name is|nombre comercial)\s*[:\-]?\s*([^,.\n]+)",
    re.IGNORECASE,
)
RE_ACTIVIDAD_LIMPIA = re.compile(
    r"(?i:(?:un|la|el|una)\s+(?:negocio|empresa)\s+de|dedicad[oa]\s+a|especialistas\s+en)\s+([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)*)"
)
RE_ACTIVIDAD_GENERAL = re.compile(
    r"(?:un negocio de|una empresa de|dedicada? a|servicios de|we do all type of|especialistas en)\s*([^,.\n]+)",
    re.IGNORECASE,
)
RE_TELEFONO_GENERICO = re.compile(
    r"(?:\+?\d{1,3}[-.\s]*)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
)
RE_UBICACION = re.compile(
    r"(?:\bubicad[oa]s?\s+en|\ben)\s+([A-Z\u00c0-\u017e][a-zA-Z\s]{1,30},\s*[A-Z\u00c0-\u017e][a-zA-Z\s]{1,30}(?:\s+\d{5})?)",
    re.IGNORECASE,
)
RE_CORREO_GENERAL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,6}\b")
RE_SEPARADOR_CAMPOS = re.compile(
    r"([^\n\r])(?=(?:(?:Nombre(?:\s+de\s+la\s+empresa)?|Licencia|Representante(?:\s+de\s+ventas)?|Ejecutivo(?:\s+de\s+ventas)?|Contacto|Propietario|Dueño|Dueno|Tel[eé]fonos?|Celulares?|Correo(?:\s+electr[oó]nico)?|Email|Servicios?(?:\s+principales)?|Ubicaci[oó]n|Sitio\s*web|Idiomas?|Languages?)\s*:|\b(?:Facebook|Instagram|TikTok|Google Play|LinkedIn|YouTube|Pinterest|HomeAdvisor|Thumbtack)|¿))",
    re.IGNORECASE,
)


def extraer_datos_html(html: str) -> tuple[str, list[str]]:
    """Usa BeautifulSoup para aislar texto limpio y enlaces de Google Lens."""
    if not html:
        return "", []
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "svg", "noscript"]):
            tag.decompose()
        enlaces: list[str] = []
        for a in soup.find_all("a", href=True):
            href = str(a["href"]).strip()
            if href.startswith("http") and not any(x in href for x in ("google.com", "policies.google.com")):
                if href not in enlaces:
                    enlaces.append(href)
        cont = soup.select_one("div[data-container-id='main-col'], div[jsname='KFl8ub'], .mZJni.Dn7Fzd")
        if not cont:
            cont = soup.select_one(".n6owBd, div[data-attrid='wa:/description'], .EyBRub") or soup
        lineas: list[str] = []
        for st in cont.select(".n6owBd strong, .n6owBd b, p strong"):
            st_t = st.get_text(separator=" ", strip=True)
            if st_t and not st_t.endswith(":") and len(st_t) > 2:
                if not any(x in st_t.lower() for x in ("información", "contacto", "imagen")):
                    lineas.append(f"Nombre de la empresa: {st_t}")
                    break
        desc_div = cont.select_one(".n6owBd, .awi2gc, div[data-attrid='wa:/description']")
        if desc_div:
            desc_cl = BeautifulSoup(str(desc_div), "html.parser")
            for sub in desc_cl(["ul", "ol", "table"]):
                sub.decompose()
            t_desc = desc_cl.get_text(separator=" ", strip=True)
            if t_desc and len(t_desc) > 5 and t_desc not in lineas:
                lineas.append(t_desc)
        for el in cont.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
            t = el.get_text(separator=" ", strip=True)
            if t and len(t) > 3 and t not in lineas:
                lineas.append(t)
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
    """Extrae entidades estructuradas mediante BeautifulSoup y diccionario semantico."""
    if isinstance(enlaces, str):
        html, enlaces = enlaces, None
    enlaces_res = list(enlaces or [])
    txt_html, enl_html = extraer_datos_html(html)
    for e in enl_html:
        if e not in enlaces_res:
            enlaces_res.append(e)

    bloques = [b.strip() for b in (texto, txt_html) if b.strip()]
    texto_total = "\n".join(bloques)
    if not texto_total:
        return FichaNegocioLens(
            id_registro=id_registro, fuente_imagen=fuente_imagen, enlaces=enlaces_res
        )
    texto_total = RE_SEPARADOR_CAMPOS.sub(r"\1\n", texto_total)

    # 1. Negocio
    negocio = ""
    m_neg = RE_ESTRUCTURADO["negocio"].search(texto_total)
    if m_neg:
        cand_n = m_neg.group(1).strip()
        if not any(cand_n.lower().startswith(x) for x in ("página de inicio", "pagina de inicio", "sitio web")):
            negocio = cand_n
    if not negocio:
        m_alt = (
            RE_NEGOCIO_LOGOTIPO.search(texto_total)
            or RE_NEGOCIO_CONTACTO.search(texto_total)
            or RE_NEGOCIO_EMPRESA_DE.search(texto_total)
            or RE_NEGOCIO_PERTENECE.search(texto_total)
            or RE_NEGOCIO.search(texto_total)
        )
        if m_alt:
            negocio = m_alt.group(1).strip()
    if negocio:
        negocio = re.sub(
            r"^(?:el\s+logotipo\s+(?:y\s+la\s+informaci[oó]n\s+de\s+contacto\s+)?de|la\s+tarjeta\s+de\s+presentaci[oó]n\s+de|informaci[oó]n\s+de\s+contacto\s+de)\s+",
            "",
            negocio,
            flags=re.IGNORECASE,
        ).strip()
        negocio = re.sub(r"\(.*?\)", "", negocio).strip()

    # 2. Propietario / Contacto
    propietario = ""
    m_prop = (
        RE_ESTRUCTURADO["propietario"].search(texto_total)
        or RE_PROPIETARIO_CUYO.search(texto_total)
        or RE_PROPIETARIO_INVERSO.search(texto_total)
        or RE_PROPIETARIO.search(texto_total)
    )
    if m_prop:
        cand = m_prop.group(1).strip()
        if cand.lower().startswith("de "):
            cand = cand[3:].strip()
        prefijos = ("la empresa", "el negocio", "una empresa", "un negocio", "de remodelacion", "servicios", "facebook", "sitio web")
        if not any(cand.lower().startswith(p) for p in prefijos):
            if cand.lower() not in ("star", "facebook", "sitio web", "google") and cand.lower() != negocio.lower():
                propietario = cand

    # 3. Licencia
    m_lic = RE_ESTRUCTURADO["licencia"].search(texto_total)
    licencia = m_lic.group(1).strip() if m_lic else ""

    # 4. Telefonos (soporte para multiples telefonos, lineas separadas y formatos internacionales)
    tels_encontrados: list[str] = []
    for m in RE_TELEFONO_GENERICO.finditer(texto_total):
        tel = m.group(0).strip()
        inicio = m.start()
        if inicio > 0 and texto_total[inicio - 1] == "+":
            tel = "+" + tel
        if tel and tel not in tels_encontrados:
            tels_encontrados.append(tel)

    if tels_encontrados:
        telefono = " / ".join(tels_encontrados)
    else:
        m_tel = RE_ESTRUCTURADO["telefono"].search(texto_total)
        telefono = m_tel.group(1).strip() if m_tel else ""
    telefono = re.sub(r"[\r\n]+", " / ", telefono)
    telefono = re.sub(r"\s*/\s*", " / ", telefono).strip(" /")

    # 5. Correo electronico
    m_cor = RE_ESTRUCTURADO["correo"].search(texto_total)
    correo = m_cor.group(1).strip() if m_cor else ""
    if not correo:
        mc = RE_CORREO_GENERAL.search(texto_total)
        correo = mc.group(0).strip() if mc else ""

    # 6. Sitio web
    m_web = RE_ESTRUCTURADO["sitio_web"].search(texto_total)
    sitio_web = m_web.group(1).strip() if m_web else ""
    if not sitio_web and enlaces_res:
        sitio_web = enlaces_res[0]
    elif sitio_web and sitio_web not in enlaces_res:
        enlaces_res.insert(0, sitio_web)

    # 7. Ubicacion
    m_ubi = RE_ESTRUCTURADO["ubicacion"].search(texto_total)
    ubicacion = m_ubi.group(1).strip() if m_ubi else ""
    if not ubicacion:
        mu = RE_UBICACION.search(texto_total)
        ubicacion = mu.group(1).strip() if mu else ""
    if ubicacion:
        ubicacion = re.split(r"\s*(?:\b(?:Facebook|Instagram|TikTok|Google Play|LinkedIn|YouTube|Pinterest|HomeAdvisor|Thumbtack)\b|¿)", ubicacion, flags=re.IGNORECASE)[0].strip()
    if ubicacion and any(x in ubicacion.lower() for x in ("exacta", "esta compañia", "esta compania", "?", "deseas", "ayude")):
        ubicacion = ""

    # 8. Categoria / Actividad
    m_cat_limp = RE_ACTIVIDAD_LIMPIA.search(texto_total)
    categoria = m_cat_limp.group(1).strip() if m_cat_limp else ""
    if not categoria:
        m_cat = RE_ESTRUCTURADO["categoria"].search(texto_total)
        if m_cat:
            categoria = m_cat.group(1).strip()
        else:
            m_gen = RE_ACTIVIDAD_GENERAL.search(texto_total)
            categoria = m_gen.group(1).strip() if m_gen else ""
    while re.search(r"\s+(?:en|de|para|con|ubicad[oa]s?)$", categoria, flags=re.IGNORECASE):
        categoria = re.sub(r"\s+(?:en|de|para|con|ubicad[oa]s?)$", "", categoria, flags=re.IGNORECASE).strip()

    # 9. Idiomas
    m_idi = RE_ESTRUCTURADO["idiomas"].search(texto_total)
    idiomas = m_idi.group(1).strip() if m_idi else ""
    if idiomas:
        idiomas = re.split(r"\s*(?:\b(?:Facebook|Instagram|TikTok|Google Play|LinkedIn|YouTube|Pinterest|HomeAdvisor|Thumbtack)\b|¿)", idiomas, flags=re.IGNORECASE)[0].strip()

    ficha = FichaNegocioLens(
        id_registro=id_registro,
        propietario=propietario,
        negocio=negocio,
        categoria=categoria,
        telefono=telefono,
        ubicacion=ubicacion,
        licencia=licencia,
        correo_electronico=correo,
        sitio_web=sitio_web,
        idiomas=idiomas,
        enlaces=enlaces_res,
        texto_sintesis=texto_total.strip(),
        fuente_imagen=fuente_imagen,
    )
    return ficha.normalizar()
