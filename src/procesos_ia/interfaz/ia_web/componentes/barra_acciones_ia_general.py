"""Barra de acciones y ejecucion con etiquetas explicativas responsivas para IA General."""

from __future__ import annotations

from typing import Callable
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from procesos_ia.interfaz.protector_botones import conectar_boton_protegido
from procesos_ia.interfaz.responsivo import ModoPantalla


class BarraAccionesIAGeneral(QWidget):
    """Agrupa botones de ejecucion con labels explicativos y adaptacion responsiva."""

    def __init__(
        self,
        al_ejecutar: Callable[[], None],
        al_cancelar: Callable[[], None],
        al_cambiar_destino: Callable[[], None],
        al_abrir_salida: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(4)

        # 1. Label informativo responsivo que explica que hace cada boton
        self.lbl_guia_acciones = QLabel(self)
        self.lbl_guia_acciones.setWordWrap(True)
        self.lbl_guia_acciones.setStyleSheet("color: #58615B; font-size: 11px;")
        layout_principal.addWidget(self.lbl_guia_acciones)

        # 2. Fila horizontal con los 4 botones principales
        layout_botones = QHBoxLayout()
        layout_botones.setSpacing(6)

        self.btn_ejecutar = QPushButton(self)
        self.btn_ejecutar.setMinimumHeight(32)
        self.btn_ejecutar.setToolTip("Conecta al navegador Chrome y ejecuta la evaluación automática por lotes.")
        conectar_boton_protegido(self.btn_ejecutar, al_ejecutar, "[INFO] Iniciando...", 800)
        layout_botones.addWidget(self.btn_ejecutar, stretch=2)

        self.btn_cancelar = QPushButton(self)
        self.btn_cancelar.setEnabled(False)
        self.btn_cancelar.setToolTip("Detiene el proceso en ejecución de forma segura sin perder los registros ya guardados.")
        conectar_boton_protegido(self.btn_cancelar, al_cancelar, tiempo_bloqueo_ms=0, auto_desbloquear=False)
        layout_botones.addWidget(self.btn_cancelar, stretch=1)

        self.btn_destino = QPushButton(self)
        self.btn_destino.setToolTip("Selecciona una carpeta personalizada para guardar el archivo resultante.")
        conectar_boton_protegido(self.btn_destino, al_cambiar_destino, tiempo_bloqueo_ms=500)
        layout_botones.addWidget(self.btn_destino, stretch=1)

        self.btn_abrir_salida = QPushButton(self)
        self.btn_abrir_salida.setToolTip("Abre directamente en el Explorador de Windows la carpeta con los CSVs enriquecidos.")
        conectar_boton_protegido(self.btn_abrir_salida, al_abrir_salida, tiempo_bloqueo_ms=800)
        layout_botones.addWidget(self.btn_abrir_salida, stretch=1)

        layout_principal.addLayout(layout_botones)
        self.adaptar_modo(ModoPantalla.ESTANDAR)

    def adaptar_modo(self, modo: ModoPantalla) -> None:
        """Ajusta etiquetas y textos de botones segun el ancho disponible."""
        if modo == ModoPantalla.COMPACTO:
            self.lbl_guia_acciones.setText("[GUÍA] Iniciar: Ejecutar IA | Detener: Parar proceso | Destino: Cambiar ruta | Salida: Ver CSV")
            self.btn_ejecutar.setText("Iniciar")
            self.btn_cancelar.setText("Detener")
            self.btn_destino.setText("Destino")
            self.btn_abrir_salida.setText("Salida")
        else:
            self.lbl_guia_acciones.setText(
                "[GUÍA DE ACCIONES] Iniciar Proceso: Ejecuta evaluación en navegador | "
                "Detener: Cancela de forma segura | "
                "Destino...: Carpeta de guardado | "
                "Abrir Salida: Abrir carpeta de resultados"
            )
            self.btn_ejecutar.setText("Iniciar Proceso en Navegador Compartido")
            self.btn_cancelar.setText("Detener")
            self.btn_destino.setText("Destino...")
            self.btn_abrir_salida.setText("Abrir Salida")
