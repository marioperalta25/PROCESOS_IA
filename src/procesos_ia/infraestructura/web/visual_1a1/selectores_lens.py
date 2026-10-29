"""Catalogo declarativo de selectores DOM para interaccion con Google Lens."""

from __future__ import annotations

SELECTORES_LENS: dict[str, list[str]] = {
    "boton_apertura": [
        "div[aria-label='Búsqueda por imagen']",
        "div[aria-label='Search by image']",
        "div[jsname='R5mgy']",
        ".etxtjc[role='button']",
        ".etxtjc",
        "#lensSearchButton",
        "button[title*='imagen']",
        "button[title*='image']",
        "button.lens",
    ],
    "disparador_subida": [
        "span[jsname='tAPGc']",
        ".DV7the[role='button']",
        ".DV7the",
        "div[jsname='QdEQIc']",
        ".f6GA0",
        ".BH9rn",
        ".ZeVBtc",
    ],
    "zonas_arrastre": [
        "div[jsname='WKe3se']",
        "div[jsname='QdEQIc']",
        ".f6GA0",
        ".BH9rn",
        ".ZeVBtc",
        ".NrdQVe",
        ".KoWHpd",
    ],
    "campo_url": [
        'input[jsname="W7hAGe"]',
        "input.cB9M7",
        'input[placeholder*="vínculo"]',
        'input[placeholder*="vinculo"]',
        'input[aria-label*="vínculo"]',
        "#inputBox",
    ],
    "boton_buscar_url": [
        'div[jsname="ZtOxCb"]',
        "div.Qwbd3",
        'div[role="button"]:has-text("Buscar")',
        "#inputSubmit",
    ],
    "contenedor_ia": [
        "div[data-subtree='aimc']",
        "div[jsname='cUzNTd']",
        ".n6owBd",
        "div[jsname='KFl8ub']",
        ".mZJni.Dn7Fzd",
        "div[data-container-id='main-col']",
        "div[data-attrid='wa:/description']",
        ".EyBRub",
        "ul.XSq4R",
    ],
    "enlaces_relacionados": [
        "a.PMDqCb",
        ".WBgIic a",
        "div.iaqvce a",
        "div.C5trKf a[target='_blank']",
        "a.alLuqe",
    ],
    "alertas_subida": [
        "div[jsname='N2QsAf']",
        "div.dEZYP[role='alert']",
        ".OHzWjb",
    ],
    "sin_vision_general": [
        "span[jsname='lGsj1']",
    ],
    "coincidencias_visuales": [
        "div[jsname='r5xl4']",
        ".Vd9M6",
        "div.G19kAf",
        "div.UAiK1e",
        "a.PMDqCb",
        "div.iaqvce",
    ],
    "sugerencias_bloqueantes": [
        ".UUbT9",
        ".aajZCb",
    ],
}
