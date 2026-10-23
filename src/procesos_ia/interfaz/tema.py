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

    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QListWidget {{
        background-color: {p.superficie};
        border: 1px solid {p.borde_control};
        border-radius: 5px;
        padding: 5px 10px;
        color: {p.texto_principal};
        selection-background-color: {p.accion_principal};
        selection-color: {p.texto_sobre_accion};
        min-height: 28px;
    }}

    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QListWidget:focus {{
        border: 1px solid {p.accion_principal};
    }}

    QListWidget::item {{
        padding: 4px 6px;
        border-radius: 3px;
    }}

    QListWidget::item:hover {{
        background-color: {p.fondo_resaltado};
    }}

    QListWidget::item:selected {{
        background-color: {p.accion_principal};
        color: {p.texto_sobre_accion};
    }}

    QPushButton {{
        background-color: {p.superficie};
        color: {p.texto_principal};
        border: 1px solid {p.borde_control};
        border-radius: 5px;
        padding: 6px 16px;
        font-weight: 500;
        min-height: 30px;
    }}

    QPushButton:hover {{
        background-color: {p.fondo_resaltado};
        border-color: {p.accion_principal};
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
        min-height: 32px;
    }}

    QPushButton#btn_principal:hover {{
        background-color: {p.accion_hover};
    }}

    QPushButton#btn_peligro {{
        background-color: {p.error};
        color: {p.texto_sobre_accion};
        border: 1px solid #75232E;
        min-height: 32px;
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

    QLabel#estado_refinamiento {{
        color: {p.texto_principal};
        font-weight: 500;
        padding: 4px 2px;
    }}

    QFrame#banner_notificacion {{
        background-color: {p.superficie};
        border: 1px solid {p.borde_control};
        border-left: 5px solid {p.borde_control};
        border-radius: 6px;
    }}

    QFrame#banner_notificacion[estado="info"] {{
        border-left: 5px solid {p.accion_hover};
        background-color: {p.fondo_resaltado};
    }}

    QFrame#banner_notificacion[estado="ok"] {{
        border-left: 5px solid {p.exito};
        background-color: {p.fondo_resaltado};
    }}

    QFrame#banner_notificacion[estado="en_proceso"] {{
        border-left: 5px solid {p.accion_principal};
        background-color: {p.fondo_resaltado};
    }}

    QFrame#banner_notificacion[estado="error"] {{
        border-left: 5px solid {p.error};
        background-color: #2D1418;
    }}

    QFrame#banner_notificacion[estado="alerta"] {{
        border-left: 5px solid {p.advertencia};
        background-color: {p.fondo_resaltado};
    }}

    QLabel#banner_mensaje {{
        color: {p.texto_principal};
        font-size: 9.5pt;
        font-weight: 600;
    }}

    QProgressBar#banner_progreso {{ background-color: {p.fondo_general}; border: 1px solid {p.borde_control}; border-radius: 3px; height: 6px; }}
    QProgressBar#banner_progreso::chunk {{ background-color: {p.accion_principal}; border-radius: 2px; }}

    QRadioButton {{ spacing: 8px; color: {p.texto_principal}; font-weight: 500; background-color: transparent; padding: 4px 6px; }}
    QRadioButton:checked {{ color: {p.accion_principal}; font-weight: 700; }}
    QRadioButton::indicator {{ width: 18px; height: 18px; border-radius: 9px; border: 2px solid {p.borde_control}; background-color: {p.superficie}; }}
    QRadioButton::indicator:hover {{ border-color: {p.accion_principal}; background-color: {p.fondo_resaltado}; }}
    QRadioButton::indicator:checked {{ border: 2px solid {p.accion_principal}; background-color: {p.accion_principal}; }}

    QCheckBox {{ spacing: 8px; color: {p.texto_principal}; background-color: transparent; padding: 2px 4px; }}
    QCheckBox:checked {{ color: {p.accion_principal}; font-weight: 600; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 2px solid {p.borde_control}; background-color: {p.superficie}; }}
    QCheckBox::indicator:hover {{ border-color: {p.accion_principal}; }}
    QCheckBox::indicator:checked {{ border: 2px solid {p.accion_principal}; background-color: {p.accion_principal}; }}

    QTabWidget::pane {{ border: 1px solid {p.borde_control}; background-color: {p.superficie}; border-radius: 6px; }}
    QTabBar::tab {{ background-color: {p.fondo_resaltado}; color: {p.texto_secundario}; border: 1px solid {p.borde_control}; padding: 7px 16px; font-weight: 600; border-top-left-radius: 5px; border-top-right-radius: 5px; margin-right: 2px; }}
    QTabBar::tab:selected {{ background-color: {p.superficie}; color: {p.accion_principal}; border-top: 3px solid {p.accion_principal}; font-weight: 700; }}
    QTabBar::tab:hover:!selected {{ background-color: {p.separador}; color: {p.texto_principal}; }}

    QFrame#barra_navegacion_subvista {{ background-color: {p.superficie}; border: 1px solid {p.borde_control}; border-radius: 6px; padding: 4px 8px; }}
    QPushButton#btn_volver_subvista {{ background-color: {p.fondo_resaltado}; color: {p.accion_principal}; border: 1px solid {p.borde_control}; font-weight: 700; padding: 5px 12px; min-height: 22px; }}
    QPushButton#btn_volver_subvista:hover {{ background-color: {p.accion_principal}; color: {p.texto_sobre_accion}; }}
    QLabel#titulo_subvista {{ font-size: 11pt; font-weight: 700; color: {p.texto_principal}; }}
    QPushButton#btn_limpiar_borrador {{ background-color: transparent; color: {p.texto_secundario}; border: 1px solid {p.borde_control}; padding: 4px 10px; min-height: 20px; font-size: 8.5pt; }}
    QPushButton#btn_limpiar_borrador:hover {{ color: {p.error}; border-color: {p.error}; }}
    """
