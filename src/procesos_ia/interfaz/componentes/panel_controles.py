"""Panel de botones de control y acciones operativas del procesamiento."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QWidget,
)

from procesos_ia.interfaz.protector_botones import conectar_boton_protegido
from procesos_ia.interfaz.responsivo import ModoPantalla


class PanelControles(QWidget):
    """Acciones principales: Iniciar, Pausar/Reanudar, Cancelar y Cuidado de Memoria."""

    solicitar_iniciar = Signal()
    solicitar_pausa = Signal()
    solicitar_reanudacion = Signal()
    solicitar_cancelacion = Signal()
    solicitar_liberar_memoria = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._esta_pausado = False
        self._en_ejecucion = False

        self._iniciar_ui()

    def _iniciar_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        # Boton Iniciar
        self.btn_iniciar = QPushButton("Iniciar Procesamiento", self)
        self.btn_iniciar.setObjectName("btn_principal")
        conectar_boton_protegido(
            self.btn_iniciar, self.solicitar_iniciar.emit,
            "[INFO] Iniciando verificación y preparación de trabajo...", tiempo_bloqueo_ms=800,
        )
        layout.addWidget(self.btn_iniciar, stretch=2)

        # Boton Pausar / Reanudar
        self.btn_pausar = QPushButton("Pausar", self)
        self.btn_pausar.setEnabled(False)
        conectar_boton_protegido(
            self.btn_pausar, self._alternar_pausa,
            "[INFO] Alternando estado de pausa...", tiempo_bloqueo_ms=500,
        )
        layout.addWidget(self.btn_pausar, stretch=1)

        # Boton Cancelar
        self.btn_cancelar = QPushButton("Cancelar", self)
        self.btn_cancelar.setObjectName("btn_peligro")
        self.btn_cancelar.setEnabled(False)
        conectar_boton_protegido(
            self.btn_cancelar, self.solicitar_cancelacion.emit,
            "[INFO] Solicitando cancelación del proceso actual...", tiempo_bloqueo_ms=1000,
        )
        layout.addWidget(self.btn_cancelar, stretch=1)

        # Boton Liberar Memoria (cuidado de hardware)
        self.btn_memoria = QPushButton("Liberar VRAM", self)
        self.btn_memoria.setToolTip("Descargar modelo de memoria VRAM (keep_alive: 0)")
        conectar_boton_protegido(
            self.btn_memoria, self.solicitar_liberar_memoria.emit,
            "[INFO] Solicitando descarga de modelo en memoria VRAM...", tiempo_bloqueo_ms=1000,
        )
        layout.addWidget(self.btn_memoria, stretch=1)

    def _alternar_pausa(self) -> None:
        if self._esta_pausado:
            self._esta_pausado = False
            self.btn_pausar.setText("Pausar")
            self.solicitar_reanudacion.emit()
        else:
            self._esta_pausado = True
            self.btn_pausar.setText("Reanudar")
            self.solicitar_pausa.emit()

    def configurar_estado_ejecucion(self, en_ejecucion: bool) -> None:
        """Adapta la disponibilidad de los botones según el estado de la tarea."""
        self._en_ejecucion = en_ejecucion
        self._esta_pausado = False

        self.btn_iniciar.setEnabled(not en_ejecucion)
        self.btn_pausar.setEnabled(en_ejecucion)
        self.btn_pausar.setText("Pausar")
        self.btn_cancelar.setEnabled(en_ejecucion)
        self.btn_memoria.setEnabled(not en_ejecucion)

    def adaptar_modo(self, modo: ModoPantalla) -> None:
        """Ajusta etiquetas y dimensiones de botones para evitar desbordes o estiramientos feos."""
        if modo == ModoPantalla.COMPACTO:
            self.btn_iniciar.setText("Iniciar")
            self.btn_memoria.setText("VRAM")
            self.btn_iniciar.setMaximumWidth(16777215)
            self.btn_pausar.setMaximumWidth(16777215)
            self.btn_cancelar.setMaximumWidth(16777215)
            self.btn_memoria.setMaximumWidth(16777215)
        elif modo == ModoPantalla.AMPLIO:
            self.btn_iniciar.setText("Iniciar Procesamiento")
            self.btn_memoria.setText("Liberar VRAM")
            self.btn_iniciar.setMaximumWidth(320)
            self.btn_pausar.setMaximumWidth(180)
            self.btn_cancelar.setMaximumWidth(180)
            self.btn_memoria.setMaximumWidth(200)
        else:
            self.btn_iniciar.setText("Iniciar Procesamiento")
            self.btn_memoria.setText("Liberar VRAM")
            self.btn_iniciar.setMaximumWidth(16777215)
            self.btn_pausar.setMaximumWidth(16777215)
            self.btn_cancelar.setMaximumWidth(16777215)
            self.btn_memoria.setMaximumWidth(16777215)
