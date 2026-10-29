"""Modulo de dominio para clasificacion semantica dinamica y extraccion de pares clave-valor."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

RE_LIMPIEZA_PUNTUACION = re.compile(r"^[\s•\-*·#\u2022\u25cf\u20230-9.\[\]]+|[\s:;]+$")
RE_CITAS_MARKDOWN = re.compile(r"\[\[\d+\](?:\([^)]*\))?\]|\[\d+\](?:\([^)]*\))?")
RE_ENLACES_MARKDOWN = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
RE_URL_SIMPLE = re.compile(r"https?://[^\s\[\]\)\>,]+|www\.[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}(?:/[^\s\[\]\)\>,]*)?")
RE_DOMINIO = re.compile(r"(?:https?://)?(?:www\.)?([a-zA-Z0-9\-]+)\.[a-zA-Z]{2,}(?:/.*)?", re.IGNORECASE)
RE_EMAIL_SIMPLE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,6}")

CORREOS_GENERICOS = {
    "gmail", "yahoo", "hotmail", "outlook", "icloud", "live", "aol", "msn",
    "proton", "protonmail", "zoho", "mail", "yandex", "gmx",
    "thumbtack", "yelp", "facebook", "instagram", "tiktok", "youtube", "linkedin",
    "nextdoor", "google", "mapquest", "homeadvisor",
}

SECCION_SERVICIOS_PATRON = re.compile(
    r"^(?:servicios(?:\s+ofrecidos|\s+principales)?|specialties|services(?:\s+offered)?|especialidades)[\s:]*$",
    re.IGNORECASE,
)


def normalizar_texto_etiqueta(texto: str) -> str:
    """Elimina acentos y caracteres especiales para comparacion de etiquetas."""
    if not texto:
        return ""
    limpio = RE_LIMPIEZA_PUNTUACION.sub("", texto).strip().lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", limpio) if unicodedata.category(c) != "Mn"
    )


def clasificar_etiqueta_semantica(etiqueta_raw: str) -> str | None:
    """Clasifica dinamicamente una etiqueta en un campo canónico del negocio."""
    norm = normalizar_texto_etiqueta(etiqueta_raw)
    if not norm:
        return None

    # 1. Correo electronico
    if any(k in norm for k in ("correo", "email", "e-mail", "mail")):
        return "correo"

    # 2. Telefono
    if any(k in norm for k in ("telefono", "phone", "celular", "mobile", "movil", "whatsapp", "tel", "fax")):
        return "telefono"

    # 3. Sitio web
    if any(k in norm for k in ("sitio web", "website", "sitio", "pagina web", "pagina", "web", "url")):
        return "sitio_web"

    # 4. Ubicacion o cobertura
    if any(k in norm for k in ("direccion", "ubicacion", "address", "location", "area principal", "area de servicio", "area", "cobertura", "zona", "ciudad", "ciudades", "estado")):
        return "ubicacion"

    # 5. Categoria o especialidad
    if any(k in norm for k in ("especialidad", "especialidades", "rubro", "actividad", "servicios ofrecidos", "servicios principales", "servicios", "servicio", "specialty", "specialties", "services offered", "services", "category", "categoria")):
        return "categoria"

    # 6. Licencia o registro
    if any(k in norm for k in ("licencia", "licencias", "license", "lic", "registro", "reg")):
        return "licencia"

    # 7. Idiomas
    if any(k in norm for k in ("idioma", "idiomas", "language", "languages")):
        return "idiomas"

    # 8. Negocio vs Propietario
    tiene_negocio = any(k in norm for k in ("negocio", "empresa", "compania", "company", "business", "contractor", "comercial", "brand", "marca"))
    tiene_prop = any(k in norm for k in ("propietario", "propietarios", "dueno", "duenos", "owner", "owners", "representante", "ejecutivo", "manager", "contacto", "agente", "vendedor"))

    if tiene_prop and not tiene_negocio:
        return "propietario"
    if tiene_negocio:
        return "negocio"
    if "nombre" in norm or "name" in norm:
        return "negocio"

    return None


RE_BLOQUE_CITAS = re.compile(r"\[\s*(?:\[?\d+\]?(?:\([^)]*\))?,?\s*)+\]")


def extraer_enlaces_y_limpiar_citas(texto: str) -> tuple[str, list[str]]:
    """Extrae URLs de markdown o citas y limpia el texto para visualizacion."""
    enlaces: list[str] = []

    # Extraer URLs en parentesis de citas o enlaces
    for m in re.finditer(r"\((https?://[^)]+)\)", texto):
        url = m.group(1).strip()
        if url not in enlaces:
            enlaces.append(url)

    # Eliminar bloques de citas completas tipo [[1](url), [2](url)] o [1]
    limpio = RE_BLOQUE_CITAS.sub("", texto)

    # Convertir markdown links [texto](url) restantes en texto
    def _sub_md(match: re.Match[str]) -> str:
        txt = match.group(1).strip()
        url = match.group(2).strip()
        if url not in enlaces:
            enlaces.append(url)
        return txt

    limpio = RE_ENLACES_MARKDOWN.sub(_sub_md, limpio)
    limpio = RE_CITAS_MARKDOWN.sub("", limpio)
    return limpio.strip(" ,;•-"), enlaces


def desglosar_valores_cruzados(campo: str, valor: str) -> tuple[dict[str, str], list[str]]:
    """Detecta enlaces o correos cruzados en campos de valor."""
    resultado: dict[str, str] = {campo: valor}
    nuevos_enlaces: list[str] = []

    if campo == "correo":
        partes = [p.strip() for p in re.split(r"[\s/]+", valor) if p.strip()]
        correos: list[str] = []
        sitios: list[str] = []
        for p in partes:
            if "@" in p:
                correos.append(p)
            elif any(x in p.lower() for x in ("www.", "http", ".com", ".org", ".net", ".io", ".co")):
                sitios.append(p)
                nuevos_enlaces.append(p)
        if correos:
            resultado["correo"] = " / ".join(correos)
        if sitios:
            resultado["sitio_web"] = " / ".join(sitios)

    elif campo == "sitio_web":
        partes = [p.strip() for p in re.split(r"[\s/]+", valor) if p.strip()]
        sitios = []
        for p in partes:
            if "@" in p:
                resultado["correo"] = p
            elif any(x in p.lower() for x in ("www.", "http", ".com", ".org", ".net", ".io", ".co")):
                sitios.append(p)
                nuevos_enlaces.append(p)
        if sitios:
            resultado["sitio_web"] = sitios[0]

    return resultado, nuevos_enlaces


def inferir_nombre_desde_dominio(dominio_o_correo: str) -> str:
    """Infiere el nombre del negocio a partir del dominio del sitio web o correo corporativo."""
    if not dominio_o_correo:
        return ""
    m = RE_DOMINIO.search(dominio_o_correo)
    if not m:
        if "@" in dominio_o_correo:
            dominio_o_correo = dominio_o_correo.split("@")[-1]
            m = RE_DOMINIO.search(dominio_o_correo)
    if m:
        slug = m.group(1).lower()
        if slug not in CORREOS_GENERICOS and len(slug) > 3:
            palabras = re.sub(r"[-_]+", " ", slug).split()
            return " ".join(p.capitalize() for p in palabras)
    return ""


def extraer_datos_semanticos_lineas(lineas: list[str]) -> tuple[dict[str, str], list[str]]:
    """Procesa lineas de texto plano extrayendo campos semanticos y enlaces."""
    datos: dict[str, str] = {}
    enlaces_encontrados: list[str] = []
    en_seccion_servicios = False
    lista_servicios: list[str] = []

    for linea_raw in lineas:
        linea = linea_raw.strip()
        if not linea:
            continue

        if SECCION_SERVICIOS_PATRON.match(linea):
            en_seccion_servicios = True
            continue

        if ":" in linea or ";" in linea:
            partes = re.split(r"[:;]", linea, maxsplit=1)
            etiqueta = partes[0].strip()
            valor_raw = partes[1].strip()

            campo = clasificar_etiqueta_semantica(etiqueta)
            if campo and valor_raw:
                en_seccion_servicios = False
                valor_limpio, urls = extraer_enlaces_y_limpiar_citas(valor_raw)
                for u in urls:
                    if u not in enlaces_encontrados:
                        enlaces_encontrados.append(u)

                cruzados, urls_cruzadas = desglosar_valores_cruzados(campo, valor_limpio)
                for u in urls_cruzadas:
                    if u not in enlaces_encontrados:
                        enlaces_encontrados.append(u)

                for k, v in cruzados.items():
                    if k not in datos or not datos[k]:
                        datos[k] = v
                continue

        if en_seccion_servicios:
            item_limpio, urls = extraer_enlaces_y_limpiar_citas(linea)
            for u in urls:
                if u not in enlaces_encontrados:
                    enlaces_encontrados.append(u)
            item_final = RE_LIMPIEZA_PUNTUACION.sub("", item_limpio).strip()
            if item_final and len(item_final) > 2:
                lista_servicios.append(item_final)

    if lista_servicios:
        servicios_str = ", ".join(lista_servicios)
        if "categoria" in datos and datos["categoria"]:
            if servicios_str not in datos["categoria"]:
                datos["categoria"] = f"{datos['categoria']} ({servicios_str})"
        else:
            datos["categoria"] = servicios_str

    return datos, enlaces_encontrados

