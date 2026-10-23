"""Banner modular y reutilizable para notificaciones, progreso y estados visuales."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class BannerNotificacion(QFrame):
    """Componente reutilizable de notificación con soporte para barra de progreso."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("banner_notificacion")
        self.setProperty("estado", "normal")

        self._iniciar_ui()

    def _iniciar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        self._label_mensaje = QLabel(self)
        self._label_mensaje.setTextFormat(Qt.TextFormat.PlainText)
        self._label_mensaje.setObjectName("banner_mensaje")
        self._label_mensaje.setWordWrap(True)
        layout.addWidget(self._label_mensaje)

        self._barra_progreso = QProgressBar(self)
        self._barra_progreso.setObjectName("banner_progreso")
        self._barra_progreso.setTextVisible(False)
        self._barra_progreso.setMaximumHeight(8)
        self._barra_progreso.setVisible(False)
        layout.addWidget(self._barra_progreso)

    @property
    def texto(self) -> str:
        return self._label_mensaje.text()

    def _aplicar_estado(self, tipo: str, texto: str) -> None:
        prefijo = f"[{tipo.upper()}] " if tipo and not texto.startswith("[") else ""
        self._label_mensaje.setText(f"{prefijo}{texto}")
        self.setProperty("estado", tipo)
        self.style().unpolish(self)
        self.style().polish(self)

    def mostrar_info(self, mensaje: str) -> None:
        self._barra_progreso.setVisible(False)
        self._aplicar_estado("info", mensaje)

    def mostrar_en_proceso(self, mensaje: str, animar: bool = True) -> None:
        if animar:
            self._barra_progreso.setRange(0, 0)
        self._barra_progreso.setVisible(True)
        self._aplicar_estado("en_proceso", mensaje)

    def mostrar_exito(self, mensaje: str) -> None:
        self._barra_progreso.setVisible(False)
        self._aplicar_estado("ok", mensaje)

    def mostrar_alerta(self, mensaje: str) -> None:
        self._barra_progreso.setVisible(False)
        self._aplicar_estado("alerta", mensaje)

    def mostrar_error(self, mensaje: str) -> None:
        self._barra_progreso.setVisible(False)
        self._aplicar_estado("error", mensaje)

    def establecer_progreso(self, actual: int, total: int) -> None:
        if total > 0:
            self._barra_progreso.setRange(0, total)
            self._barra_progreso.setValue(actual)
            self._barra_progreso.setVisible(True)

    def limpiar(self) -> None:
        self._barra_progreso.setVisible(False)
        self._label_mensaje.clear()
        self.setProperty("estado", "normal")
        self.style().unpolish(self)
        self.style().polish(self)
