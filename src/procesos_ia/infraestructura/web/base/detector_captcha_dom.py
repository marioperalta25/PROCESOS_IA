"""Utilidades compartidas de infraestructura para deteccion rapida de CAPTCHA en DOM."""

from __future__ import annotations

from typing import Any

SELECTORES_CAPTCHA_DOM = (
    "#captcha-form, form[action*='sorry'], #recaptcha, .g-recaptcha, iframe[src*='recaptcha']"
)

JS_CONDICION_CAPTCHA = (
    '((location.href || "").toLowerCase().includes("/sorry/")'
    ' || (location.href || "").toLowerCase().includes("sorry/index")'
    f' || Boolean(document.querySelector("{SELECTORES_CAPTCHA_DOM}")))'
)

PATRONES_TEXTO_CAPTCHA = (
    "tráfico inusual",
    "trafico inusual",
    "unusual traffic",
)


def es_url_captcha(pestana_o_url: Any) -> bool:
    """Retorna True si la pestana o cadena URL corresponde a la pantalla /sorry/ de Google."""
    url = pestana_o_url if isinstance(pestana_o_url, str) else getattr(pestana_o_url, "url", "")
    url_low = str(url or "").lower()
    return "/sorry/" in url_low or "sorry/index" in url_low


def contiene_texto_captcha(texto: str) -> bool:
    """Retorna True si el texto extraido corresponde al aviso de trafico inusual de Google."""
    if not texto:
        return False
    low = texto.lower()
    return any(patron in low for patron in PATRONES_TEXTO_CAPTCHA)
