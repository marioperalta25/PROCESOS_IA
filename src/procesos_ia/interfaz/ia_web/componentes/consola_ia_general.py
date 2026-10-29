"""Componente de bitacora y consola de eventos en tiempo real para IA General."""

from __future__ import annotations

from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ConsolaIAGeneral(QGroupBox):
    """Consola para visualizacion de registros, lotes y estados de ejecucion."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Bitácora de Lotes y Procesamiento en Vivo", parent)
        self._iniciar_ui()

    def _iniciar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        layout_top = QHBoxLayout()
        layout_top.addStretch()
        self.btn_limpiar = QPushButton("Limpiar Bitácora", self)
        self.btn_limpiar.setMinimumWidth(130)
        self.btn_limpiar.setMinimumHeight(26)
        self.btn_limpiar.clicked.connect(self.limpiar)
        layout_top.addWidget(self.btn_limpiar)
        layout.addLayout(layout_top)

        self._altura_actual = 120
        self.texto_log = QPlainTextEdit(self)
        self.texto_log.setReadOnly(True)
        self.texto_log.setMaximumBlockCount(1000)
        self.texto_log.setFixedHeight(self._altura_actual)
        self.texto_log.setStyleSheet(
            "QPlainTextEdit { background-color: #1E2024; color: #E8EAF2; "
            "font-family: Consolas, monospace; font-size: 10pt; border-radius: 4px; }"
        )
        layout.addWidget(self.texto_log)

        from procesos_ia.interfaz.componentes.tirador_ajustable import TiradorRedimensionVertical
        self.tirador = TiradorRedimensionVertical(
            widget_objetivo=self.texto_log,
            altura_min=90,
            altura_max=380,
            callback_cambio=lambda h: setattr(self, "_altura_actual", h),
            parent=self,
        )
        layout.addWidget(self.tirador)

    def _establecer_altura(self, nueva: int) -> None:
        self._altura_actual = max(90, min(380, nueva))
        self.texto_log.setFixedHeight(self._altura_actual)

    def _expandir_altura(self) -> None:
        self._establecer_altura(self._altura_actual + 60)

    def _contraer_altura(self) -> None:
        self._establecer_altura(self._altura_actual - 60)

    def agregar_log(self, mensaje: str) -> None:
        """Agrega una linea a la consola con marca temporal."""
        ahora = datetime.now().strftime("%H:%M:%S")
        linea = f"[{ahora}] {mensaje}"
        self.texto_log.appendPlainText(linea)
        self.texto_log.moveCursor(QTextCursor.MoveOperation.End)

    def limpiar(self) -> None:
        """Limpia el contenido visible de la bitacora."""
        self.texto_log.clear()
        self.agregar_log("[INFO] Bitácora reiniciada.")
