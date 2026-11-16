"""Panel compacto de opciones para Modo IA con CSV de URLs por lotes."""

from __future__ import annotations

from typing import Any
from PySide6.QtWidgets import (
    QCheckBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from procesos_ia.aplicacion.ia_web.conversacional.constructor_prompt_imagenes import CAMPOS_DISPONIBLES
from procesos_ia.interfaz.componentes.editor_texto_expandible import EditorTextoExpandible
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido


class PanelModoIAUrls(QWidget):
    """Permite elegir campos a extraer, tamano de lote y rotacion de chat para URLs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checks: dict[str, QCheckBox] = {}
        self._iniciar_ui()

    def _iniciar_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        grupo = QGroupBox("Opciones de Extracción y Lotes (Modo IA por URLs)", self)
        lay_g = QVBoxLayout(grupo)
        lay_g.setContentsMargins(8, 8, 8, 8)
        lay_g.setSpacing(6)

        lay_top = QHBoxLayout()
        lay_top.addWidget(QLabel("Campos a extraer de cada URL:", self))
        lay_top.addStretch()
        self.btn_todas = QPushButton("Todas", self)
        self.btn_ninguna = QPushButton("Ninguna", self)
        conectar_boton_protegido(self.btn_todas, lambda: self._marcar(True), "[INFO] Marcando campos...", 300)
        conectar_boton_protegido(self.btn_ninguna, lambda: self._marcar(False), "[INFO] Desmarcando campos...", 300)
        lay_top.addWidget(self.btn_todas)
        lay_top.addWidget(self.btn_ninguna)
        lay_g.addLayout(lay_top)

        lay_chk = QHBoxLayout()
        for clave, info in CAMPOS_DISPONIBLES.items():
            chk = QCheckBox(info["etiqueta"], self)
            chk.setChecked(True)
            self._checks[clave] = chk
            lay_chk.addWidget(chk)
        lay_g.addLayout(lay_chk)

        lay_lotes = QHBoxLayout()
        lay_lotes.addWidget(QLabel("URLs por lote:", self))
        self.spin_lote = QSpinBox(self)
        self.spin_lote.setRange(1, 25); self.spin_lote.setValue(3)
        lay_lotes.addWidget(self.spin_lote)
        lay_lotes.addWidget(QLabel("Lotes por conversación:", self))
        self.spin_lotes_conv = QSpinBox(self)
        self.spin_lotes_conv.setRange(1, 20); self.spin_lotes_conv.setValue(4)
        lay_lotes.addWidget(self.spin_lotes_conv)
        lay_lotes.addStretch()
        lay_g.addLayout(lay_lotes)

        self.txt_instrucciones_extra = EditorTextoExpandible(
            placeholder="Instrucciones adicionales opcionales para el lote de URLs...",
            altura_min=55, altura_max=160, parent=self,
        )
        lay_g.addWidget(self.txt_instrucciones_extra)
        lay.addWidget(grupo)

    def _marcar(self, estado: bool) -> None:
        for chk in self._checks.values():
            chk.setChecked(estado)

    def obtener_parametros(self) -> dict[str, Any]:
        return {
            "campos_activos": [k for k, chk in self._checks.items() if chk.isChecked()],
            "tamano_lote": self.spin_lote.value(),
            "lotes_por_conversacion": self.spin_lotes_conv.value(),
            "instrucciones_extra": self.txt_instrucciones_extra.toPlainText().strip(),
        }

    def limpiar(self) -> None:
        self._marcar(True)
        self.spin_lote.setValue(3)
        self.spin_lotes_conv.setValue(4)
        self.txt_instrucciones_extra.clear()
