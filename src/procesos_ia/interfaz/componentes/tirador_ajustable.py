"""Componente tirador de redimensionamiento vertical con cursor SizeVerCursor."""

from __future__ import annotations

from typing import Callable
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QLayout, QWidget


class TiradorRedimensionVertical(QWidget):
    """Barra divisoria inferior interactiva que cambia el cursor a SizeVerCursor y redimensiona."""

    altura_cambiada = Signal(int)

    def __init__(
        self,
        widget_objetivo: QWidget,
        altura_min: int = 70,
        altura_max: int = 400,
        callback_cambio: Callable[[int], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.widget_objetivo = widget_objetivo
        self.altura_min = altura_min
        self.altura_max = altura_max
        self.callback_cambio = callback_cambio

        self._arrastrando = False
        self._pos_inicial_y = 0
        self._altura_inicial = 0
        self._hover = False

        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setFixedHeight(10)
        self.setToolTip("Haga clic y arrastre verticalmente para ajustar la altura")

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color_linea = QColor(190, 190, 190, 220) if self._hover else QColor(140, 140, 140, 130)
        pen = QPen(color_linea)
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        centro_x = self.width() // 2
        y = self.height() // 2
        painter.drawLine(centro_x - 22, y, centro_x + 22, y)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._arrastrando = True
            self._pos_inicial_y = event.globalPosition().toPoint().y()
            self._altura_inicial = self.widget_objetivo.height()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._arrastrando:
            delta_y = event.globalPosition().toPoint().y() - self._pos_inicial_y
            nueva_altura = max(self.altura_min, min(self.altura_max, self._altura_inicial + delta_y))
            self.widget_objetivo.setFixedHeight(nueva_altura)
            self.altura_cambiada.emit(nueva_altura)
            if self.callback_cambio:
                self.callback_cambio(nueva_altura)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._arrastrando = False
            event.accept()


def adjuntar_tirador_redimension(
    layout: QLayout,
    widget_objetivo: QWidget,
    altura_min: int = 70,
    altura_max: int = 400,
    callback_cambio: Callable[[int], None] | None = None,
) -> TiradorRedimensionVertical:
    """Helper que crea un tirador de arrastre y lo inserta en el layout justo debajo del widget."""
    tirador = TiradorRedimensionVertical(
        widget_objetivo=widget_objetivo,
        altura_min=altura_min,
        altura_max=altura_max,
        callback_cambio=callback_cambio,
        parent=widget_objetivo.parentWidget(),
    )
    layout.addWidget(tirador)
    return tirador
