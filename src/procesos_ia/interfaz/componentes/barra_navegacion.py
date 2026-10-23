"""Barra superior de navegación para subvistas integradas en la ventana principal."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)


from procesos_ia.interfaz.protector_botones import conectar_boton_protegido


class BarraNavegacionSubvista(QFrame):
    """Barra superior con botón de regreso, título de sección y botón de reinicio de borrador."""

    volver_solicitado = Signal()
    limpiar_solicitado = Signal()

    def __init__(
        self,
        titulo: str,
        texto_limpiar: str = "Limpiar borrador",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("barra_navegacion_subvista")
        self._iniciar_ui(titulo, texto_limpiar)

    def _iniciar_ui(self, titulo: str, texto_limpiar: str) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        self.btn_volver = QPushButton("[<- Volver]", self)
        self.btn_volver.setObjectName("btn_volver_subvista")
        self.btn_volver.setToolTip("Regresar a la pantalla principal sin perder cambios en curso")
        conectar_boton_protegido(
            self.btn_volver, self.volver_solicitado.emit,
            "[INFO] Regresando a la vista principal...", tiempo_bloqueo_ms=600,
        )
        layout.addWidget(self.btn_volver)

        self.label_titulo = QLabel(titulo, self)
        self.label_titulo.setObjectName("titulo_subvista")
        layout.addWidget(self.label_titulo, stretch=1)

        self.btn_limpiar = QPushButton(f"[0] {texto_limpiar}", self)
        self.btn_limpiar.setObjectName("btn_limpiar_borrador")
        self.btn_limpiar.setToolTip("Descarta los cambios temporales no guardados e inicia de cero")
        conectar_boton_protegido(
            self.btn_limpiar, self.limpiar_solicitado.emit,
            "[INFO] Restableciendo valores desde cero...", tiempo_bloqueo_ms=600,
        )
        layout.addWidget(self.btn_limpiar)

    def establecer_titulo(self, titulo: str) -> None:
        self.label_titulo.setText(titulo)
