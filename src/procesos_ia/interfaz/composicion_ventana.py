"""Construccion de los paneles y distribucion visual de la ventana."""

from PySide6.QtWidgets import QMainWindow, QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from procesos_ia.interfaz.componentes.panel_archivos import PanelArchivos
from procesos_ia.interfaz.componentes.panel_configuracion import PanelConfiguracionIA
from procesos_ia.interfaz.componentes.panel_controles import PanelControles
from procesos_ia.interfaz.componentes.panel_encabezado import PanelEncabezado
from procesos_ia.interfaz.componentes.panel_telemetria import PanelTelemetria
from procesos_ia.interfaz.recursos import GestorRecursos
from procesos_ia.interfaz.tema import PaletaVisual


def construir_paneles(
    ventana: QMainWindow, recursos: GestorRecursos, paleta: PaletaVisual,
) -> None:
    widget_central = QWidget(ventana)
    ventana.setCentralWidget(widget_central)

    layout_contenedor = QVBoxLayout(widget_central)
    layout_contenedor.setContentsMargins(0, 0, 0, 0)
    layout_contenedor.setSpacing(0)

    ventana.pila_vistas = QStackedWidget(widget_central)
    layout_contenedor.addWidget(ventana.pila_vistas)

    ventana.vista_principal = QWidget(ventana.pila_vistas)
    layout_central = QVBoxLayout(ventana.vista_principal)
    layout_central.setContentsMargins(12, 10, 12, 10)
    layout_central.setSpacing(8)

    ventana.panel_encabezado = PanelEncabezado(recursos, paleta, ventana)
    layout_central.addWidget(ventana.panel_encabezado)

    area_scroll = QScrollArea(ventana)
    area_scroll.setWidgetResizable(True)
    area_scroll.setFrameShape(QScrollArea.Shape.NoFrame)

    contenido_scroll = QWidget()
    layout_scroll = QVBoxLayout(contenido_scroll)
    layout_scroll.setContentsMargins(0, 0, 0, 0)
    layout_scroll.setSpacing(10)

    enrutador = getattr(ventana, "_enrutador", None)
    ventana.panel_archivos = PanelArchivos(ventana, enrutador=enrutador)
    ventana.panel_configuracion = PanelConfiguracionIA(ventana)
    ventana.panel_telemetria = PanelTelemetria(paleta, ventana)
    for panel in (ventana.panel_archivos, ventana.panel_configuracion, ventana.panel_telemetria):
        layout_scroll.addWidget(panel)

    layout_scroll.addStretch()
    area_scroll.setWidget(contenido_scroll)
    layout_central.addWidget(area_scroll, stretch=1)

    ventana.panel_controles = PanelControles(ventana)
    layout_central.addWidget(ventana.panel_controles)

    ventana.pila_vistas.addWidget(ventana.vista_principal)
