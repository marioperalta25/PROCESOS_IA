"""Valores visuales centralizados y hojas de estilo para la interfaz de escritorio."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PaletaVisual:
    """Valores de color de la dirección visual sobria y accesible."""

    fondo_general: str = "#F4F0E8"
    superficie: str = "#FFFCF7"
    texto_principal: str = "#222C2A"
    texto_secundario: str = "#58615B"
    accion_principal: str = "#9A472E"
    accion_hover: str = "#7E3924"
    texto_sobre_accion: str = "#FFFCF7"
    borde_control: str = "#D9D1C5"
    separador: str = "#E2DDD5"
    exito: str = "#326457"
    advertencia: str = "#7A511B"
    error: str = "#962F3C"
    fondo_resaltado: str = "#EDE7DC"
    barra_progreso_fondo: str = "#E0D9CE"


def construir_hoja_estilos(paleta: PaletaVisual | None = None) -> str:
    """Construye la hoja de estilos Qt (QSS) aplicando la paleta centralizada."""
    p = paleta or PaletaVisual()

    return f"""
    QWidget {{
        background-color: {p.fondo_general};
        color: {p.texto_principal};
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        font-size: 10pt;
    }}

    QGroupBox {{
        background-color: {p.superficie};
        border: 1px solid {p.borde_control};
        border-radius: 6px;
        margin-top: 1.2em;
        padding: 14px 10px 10px 10px;
        font-weight: 600;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 6px;
        color: {p.texto_principal};
    }}

    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {p.superficie};
        border: 1px solid {p.borde_control};
        border-radius: 4px;
        padding: 5px 8px;
        color: {p.texto_principal};
        selection-background-color: {p.accion_principal};
        selection-color: {p.texto_sobre_accion};
    }}

    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
        border: 1px solid {p.accion_principal};
    }}

    QPushButton {{
        background-color: {p.superficie};
        color: {p.texto_principal};
        border: 1px solid {p.borde_control};
        border-radius: 4px;
        padding: 6px 14px;
        font-weight: 500;
        min-height: 22px;
    }}

    QPushButton:hover {{
        background-color: {p.fondo_resaltado};
    }}

    QPushButton:pressed {{
        background-color: {p.separador};
    }}

    QPushButton:disabled {{
        color: {p.texto_secundario};
        background-color: {p.fondo_general};
        border-color: {p.separador};
    }}

    QPushButton#btn_principal {{
        background-color: {p.accion_principal};
        color: {p.texto_sobre_accion};
        border: 1px solid {p.accion_hover};
        font-weight: 600;
    }}

    QPushButton#btn_principal:hover {{
        background-color: {p.accion_hover};
    }}

    QPushButton#btn_peligro {{
        background-color: {p.error};
        color: {p.texto_sobre_accion};
        border: 1px solid #75232E;
    }}

    QPushButton#btn_peligro:hover {{
        background-color: #75232E;
    }}

    QProgressBar {{
        background-color: {p.barra_progreso_fondo};
        border: 1px solid {p.borde_control};
        border-radius: 4px;
        text-align: center;
        color: {p.texto_principal};
        font-weight: 600;
        height: 18px;
    }}

    QProgressBar::chunk {{
        background-color: {p.accion_principal};
        border-radius: 3px;
    }}

    QScrollBar:vertical {{
        background: {p.fondo_general};
        width: 10px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background: {p.borde_control};
        min-height: 20px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {p.texto_secundario};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QLabel#titulo_principal {{
        font-size: 15pt;
        font-weight: 700;
        color: {p.texto_principal};
    }}

    QLabel#subtitulo {{
        color: {p.texto_secundario};
        font-size: 9pt;
    }}

    QLabel#estado_pill {{
        background-color: {p.fondo_resaltado};
        border: 1px solid {p.borde_control};
        border-radius: 12px;
        padding: 4px 10px;
        font-weight: 600;
        font-size: 8.5pt;
    }}
    """
