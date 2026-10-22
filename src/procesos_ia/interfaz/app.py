"""Punto de entrada para la aplicación de escritorio PROCESOS_IA."""

from __future__ import annotations

import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from procesos_ia.interfaz.recursos import GestorRecursos
from procesos_ia.interfaz.ventana_principal import VentanaPrincipal


def crear_aplicacion(argumentos: list[str] | None = None) -> QApplication:
    """Crea y configura la instancia de QApplication con soporte de alta densidad."""
    # Configurar escalado y soporte de alta densidad antes de instanciar
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    args = argumentos if argumentos is not None else sys.argv
    app = QApplication.instance() or QApplication(args)
    app.setApplicationName("PROCESOS_IA")
    app.setOrganizationName("PROCESOS_IA")

    recursos = GestorRecursos()
    app.setWindowIcon(recursos.obtener_icono_aplicacion())

    return app


def ejecutar_interfaz(argumentos: list[str] | None = None) -> int:
    """Arranca el bucle de eventos principal de la interfaz gráfica."""
    app = crear_aplicacion(argumentos)
    ventana = VentanaPrincipal()
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(ejecutar_interfaz())
