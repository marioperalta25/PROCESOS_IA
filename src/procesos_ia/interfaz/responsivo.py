"""Lógica de responsividad y adaptación de distribución según el tamaño de la ventana."""

from __future__ import annotations

from enum import Enum
from PySide6.QtWidgets import QHeaderView, QTableWidget, QWidget


class ModoPantalla(str, Enum):
    COMPACTO = "compacto"      # ancho < 820px
    ESTANDAR = "estandar"      # 820px <= ancho < 1250px
    AMPLIO = "amplio"          # ancho >= 1250px


UMBRAL_COMPACTO: int = 820
UMBRAL_AMPLIO: int = 1250


def determinar_modo_pantalla(ancho: int) -> ModoPantalla:
    """Clasifica el ancho disponible de la ventana en una categoría responsiva."""
    if ancho < UMBRAL_COMPACTO:
        return ModoPantalla.COMPACTO
    if ancho >= UMBRAL_AMPLIO:
        return ModoPantalla.AMPLIO
    return ModoPantalla.ESTANDAR


def configurar_tabla_responsiva(
    tabla: QTableWidget,
    columnas_fijas: dict[int, int] | None = None,
    columna_expandible: int | None = None,
) -> None:
    """Configura cabeceras y políticas para que las tablas no se deformen en anchos variables."""
    encabezado = tabla.horizontalHeader()
    encabezado.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

    if columnas_fijas:
        for col, ancho in columnas_fijas.items():
            if col < tabla.columnCount():
                tabla.setColumnWidth(col, ancho)

    if columna_expandible is not None and columna_expandible < tabla.columnCount():
        encabezado.setSectionResizeMode(columna_expandible, QHeaderView.ResizeMode.Stretch)
    else:
        encabezado.setStretchLastSection(True)


def aplicar_limites_control(
    widget: QWidget,
    ancho_minimo: int | None = None,
    ancho_maximo: int | None = None,
) -> None:
    """Aplica límites para que los controles no se aplasten ni se estiren desproporcionadamente."""
    if ancho_minimo is not None:
        widget.setMinimumWidth(ancho_minimo)
    if ancho_maximo is not None:
        widget.setMaximumWidth(ancho_maximo)


ALTURA_INPUT_TEXTO_MIN: int = 80
ALTURA_INPUT_TEXTO_MAX: int = 380
ALTURA_INPUT_TEXTO_DEFECTO: int = 125

ALTURA_BITACORA_MIN: int = 95
ALTURA_BITACORA_MAX: int = 380
ALTURA_BITACORA_DEFECTO: int = 135


def aplicar_limites_altura_control(
    widget: QWidget,
    altura_minima: int = ALTURA_INPUT_TEXTO_MIN,
    altura_maxima: int = ALTURA_INPUT_TEXTO_MAX,
    altura_inicial: int | None = ALTURA_INPUT_TEXTO_DEFECTO,
) -> None:
    """Configura límites verticales para inputs multilínea y bitácoras evitando deformaciones."""
    widget.setMinimumHeight(altura_minima)
    widget.setMaximumHeight(altura_maxima)
    if altura_inicial is not None:
        widget.resize(widget.width(), altura_inicial)

