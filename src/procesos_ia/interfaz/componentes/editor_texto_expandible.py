"""Editor de texto multilínea con tirador de arrastre inferior (cursor SizeVerCursor)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from procesos_ia.interfaz.componentes.tirador_ajustable import TiradorRedimensionVertical
from procesos_ia.interfaz.responsivo import (
    ALTURA_INPUT_TEXTO_DEFECTO,
    ALTURA_INPUT_TEXTO_MAX,
    ALTURA_INPUT_TEXTO_MIN,
)


class EditorTextoExpandible(QWidget):
    """Área de texto editable con tirador inferior arrastrable sin botones."""

    texto_cambiado = Signal()
    textChanged = texto_cambiado
    altura_cambiada = Signal(int)

    def __init__(
        self,
        altura_inicial: int = ALTURA_INPUT_TEXTO_DEFECTO,
        altura_min: int | str = ALTURA_INPUT_TEXTO_MIN,
        altura_max: int | QWidget = ALTURA_INPUT_TEXTO_MAX,
        placeholder: str = "",
        parent: QWidget | None = None,
    ) -> None:
        if isinstance(altura_min, str):
            placeholder = altura_min
            altura_min = ALTURA_INPUT_TEXTO_MIN
            if isinstance(altura_max, QWidget):
                parent = altura_max
                altura_max = ALTURA_INPUT_TEXTO_MAX
        elif isinstance(placeholder, QWidget) and parent is None:
            parent = placeholder
            placeholder = ""

        super().__init__(parent)
        self._altura_min = int(altura_min)
        self._altura_max = int(altura_max) if isinstance(altura_max, int) else ALTURA_INPUT_TEXTO_MAX
        self._altura_actual = altura_inicial

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.editor = QTextEdit(self)
        self.editor.setPlaceholderText(placeholder)
        self.editor.setFixedHeight(self._altura_actual)
        self.editor.textChanged.connect(self.texto_cambiado.emit)
        layout.addWidget(self.editor)

        # Tirador inferior directo donde el cursor cambia a SizeVerCursor (flecha arriba/abajo)
        self.tirador = TiradorRedimensionVertical(
            widget_objetivo=self.editor,
            altura_min=self._altura_min,
            altura_max=self._altura_max,
            callback_cambio=self._al_cambiar_altura,
            parent=self,
        )
        layout.addWidget(self.tirador)
        self.setMinimumHeight(self._altura_actual + 14)

    def _al_cambiar_altura(self, nueva: int) -> None:
        self._altura_actual = nueva
        margen = self.tirador.height() if hasattr(self, "tirador") else 12
        self.setMinimumHeight(nueva + margen + 2)
        self.updateGeometry()
        p = self.parentWidget()
        while p is not None:
            p.updateGeometry()
            lay = p.layout()
            if lay is not None:
                lay.activate()
            p = p.parentWidget()
        self.altura_cambiada.emit(nueva)

    def _expandir_altura(self) -> None:
        """Compatibilidad programatica para tests."""
        nueva = min(self._altura_max, self._altura_actual + 60)
        self.editor.setFixedHeight(nueva)
        self._al_cambiar_altura(nueva)

    def _contraer_altura(self) -> None:
        """Compatibilidad programatica para tests."""
        nueva = max(self._altura_min, self._altura_actual - 60)
        self.editor.setFixedHeight(nueva)
        self._al_cambiar_altura(nueva)

    def toPlainText(self) -> str:
        return self.editor.toPlainText()

    def setPlainText(self, texto: str) -> None:
        self.editor.setPlainText(texto)

    def setPlaceholderText(self, placeholder: str) -> None:
        self.editor.setPlaceholderText(placeholder)

    def clear(self) -> None:
        self.editor.clear()
