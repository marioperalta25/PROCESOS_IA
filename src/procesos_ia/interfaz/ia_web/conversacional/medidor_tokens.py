"""Medidor y validador de caracteres y tokens en tiempo real para Modo IA."""

from __future__ import annotations

from typing import Any
from PySide6.QtWidgets import QLabel

from procesos_ia.interfaz.responsivo import ModoPantalla

LIMITE_CARACTERES_MODO_IA = 8000


def estimar_tokens_texto(texto: str) -> int:
    """Calcula una estimacion aproximada de tokens para modelos multilingues (~3.8 caracteres por token)."""
    if not texto:
        return 0
    return max(1, round(len(texto) / 3.8))


def evaluar_salud_prompt(texto: str) -> dict[str, Any]:
    """Evalua la longitud de las instrucciones contra los limites de Google Modo IA."""
    chars = len(texto)
    tokens = estimar_tokens_texto(texto)

    if chars == 0:
        return {
            "chars": 0, "tokens": 0, "estado": "vacio",
            "mensaje": "[INFO] 0 / 8,000 caracteres (~0 tokens) - Ingrese o seleccione instrucciones",
            "mensaje_compacto": "[INFO] 0/8k car",
            "estilo": "color: #58615B; font-size: 11px;",
        }
    if chars <= 6500:
        return {
            "chars": chars, "tokens": tokens, "estado": "seguro",
            "mensaje": f"[OK] {chars:,} / {LIMITE_CARACTERES_MODO_IA:,} caracteres (~{tokens:,} tokens) - Estado: Seguro",
            "mensaje_compacto": f"[OK] {chars/1000:.1f}k/8k car (~{tokens} tok)",
            "estilo": "color: #2e7d32; font-size: 11px; font-weight: bold;",
        }
    if chars <= LIMITE_CARACTERES_MODO_IA:
        return {
            "chars": chars, "tokens": tokens, "estado": "alerta",
            "mensaje": f"[ALERTA] {chars:,} / {LIMITE_CARACTERES_MODO_IA:,} caracteres (~{tokens:,} tokens) - Próximo al límite",
            "mensaje_compacto": f"[ALERTA] {chars/1000:.1f}k/8k car",
            "estilo": "color: #ed6c02; font-size: 11px; font-weight: bold;",
        }
    exceso = chars - LIMITE_CARACTERES_MODO_IA
    return {
        "chars": chars, "tokens": tokens, "estado": "peligro",
        "mensaje": f"[ERROR] {chars:,} / {LIMITE_CARACTERES_MODO_IA:,} caracteres (~{tokens:,} tokens) - Excede por {exceso:,} caracteres",
        "mensaje_compacto": f"[ERROR] Excede +{exceso} car",
        "estilo": "color: #d32f2f; font-size: 11px; font-weight: bold;",
    }


class EtiquetaContadorTokens(QLabel):
    """Etiqueta responsiva con telemetria en vivo de caracteres y tokens del prompt."""

    def __init__(self, parent: QLabel | None = None) -> None:
        super().__init__(parent)
        self.setWordWrap(True)
        self._modo = ModoPantalla.ESTANDAR
        self._ultimo_texto = ""
        self.actualizar("")

    def actualizar(self, texto: str) -> dict[str, Any]:
        """Actualiza el texto y estilo visual segun la longitud calculada."""
        self._ultimo_texto = texto
        evaluacion = evaluar_salud_prompt(texto)
        msg = evaluacion["mensaje_compacto"] if self._modo == ModoPantalla.COMPACTO else evaluacion["mensaje"]
        self.setText(msg)
        self.setStyleSheet(evaluacion["estilo"])
        return evaluacion

    def adaptar_modo(self, modo: ModoPantalla) -> None:
        """Adapta la visualizacion al modo de pantalla compacto o extendido."""
        self._modo = modo
        self.actualizar(self._ultimo_texto)
