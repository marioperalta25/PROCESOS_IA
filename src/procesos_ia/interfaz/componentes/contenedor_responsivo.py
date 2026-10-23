"""Contenedor base general responsivo con scroll automatico y adaptacion de modo."""

from __future__ import annotations

from typing import Any
from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QResizeEvent, QWheelEvent
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QFrame,
    QLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from procesos_ia.interfaz.responsivo import (
    ModoPantalla,
    determinar_modo_pantalla,
)


class FiltroScrollSegmentado(QObject):
    """Filtro de rueda de raton para coordinar scrolls anidados con el scroll general."""

    def __init__(self, scroll_general: QScrollArea, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._scroll_general = scroll_general

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Wheel:
            sb_hijo = None
            if isinstance(obj, QAbstractScrollArea):
                sb_hijo = obj.verticalScrollBar()
            elif hasattr(obj, "parent") and isinstance(obj.parent(), QAbstractScrollArea):
                sb_hijo = obj.parent().verticalScrollBar()

            delta_y = event.angleDelta().y() if hasattr(event, "angleDelta") else 0

            # Caso 1: El control interno cabe completamente (no requiere scroll interno)
            if sb_hijo is None or sb_hijo.maximum() <= sb_hijo.minimum():
                self._propagar_a_general(delta_y)
                return True

            # Caso 2: El usuario sube y el control interno ya esta al inicio
            if delta_y > 0 and sb_hijo.value() <= sb_hijo.minimum():
                self._propagar_a_general(delta_y)
                return True

            # Caso 3: El usuario baja y el control interno ya llego al final
            if delta_y < 0 and sb_hijo.value() >= sb_hijo.maximum():
                self._propagar_a_general(delta_y)
                return True

            # Caso 4: El control interno tiene margen para desplazarse en esa direccion
            return False

        return super().eventFilter(obj, event)

    def _propagar_a_general(self, delta_y: int) -> None:
        if self._scroll_general is None:
            return
        sb_gen = self._scroll_general.verticalScrollBar()
        if sb_gen is None or sb_gen.maximum() <= sb_gen.minimum():
            return
        paso = int((delta_y / 120.0) * sb_gen.singleStep() * 3)
        sb_gen.setValue(sb_gen.value() - paso)


class ContenedorPantallaResponsiva(QWidget):
    """Contenedor general con scroll vertical y notificacion de modo responsivo."""

    modo_cambiado = Signal(object)  # Emite ModoPantalla

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._modo_actual: ModoPantalla = ModoPantalla.ESTANDAR
        self._iniciar_ui()

    def _iniciar_ui(self) -> None:
        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.widget_contenido = QWidget()
        self.layout_contenido = QVBoxLayout(self.widget_contenido)
        self.layout_contenido.setContentsMargins(10, 8, 10, 8)
        self.layout_contenido.setSpacing(8)

        self.scroll_area.setWidget(self.widget_contenido)
        layout_raiz.addWidget(self.scroll_area)
        self._filtro_scroll = FiltroScrollSegmentado(self.scroll_area, self)

    def agregar_widget(self, widget: QWidget, stretch: int = 0) -> None:
        """Agrega un control asegurando que respete el flujo vertical responsivo."""
        self.layout_contenido.addWidget(widget, stretch)
        self._instalar_filtro_segmentado(widget)

    def agregar_layout(self, layout: QLayout) -> None:
        """Agrega un sub-layout horizontal o formulario al flujo vertical."""
        self.layout_contenido.addLayout(layout)

    def agregar_espaciador(self) -> None:
        """Agrega un espacio elastico inferior al final de los controles."""
        self.layout_contenido.addStretch()

    def _instalar_filtro_segmentado(self, widget: QWidget) -> None:
        """Instala el filtro de rueda en el widget y sus areas de scroll internas."""
        if isinstance(widget, QAbstractScrollArea):
            widget.installEventFilter(self._filtro_scroll)
            if widget.viewport():
                widget.viewport().installEventFilter(self._filtro_scroll)
        for hijo in widget.findChildren(QAbstractScrollArea):
            hijo.installEventFilter(self._filtro_scroll)
            if hijo.viewport():
                hijo.viewport().installEventFilter(self._filtro_scroll)

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        for area in self.widget_contenido.findChildren(QAbstractScrollArea):
            area.installEventFilter(self._filtro_scroll)
            if area.viewport():
                area.viewport().installEventFilter(self._filtro_scroll)

    @property
    def modo_actual(self) -> ModoPantalla:
        return self._modo_actual

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        ancho = event.size().width()
        nuevo_modo = determinar_modo_pantalla(ancho)
        if nuevo_modo != self._modo_actual:
            self._modo_actual = nuevo_modo
            self.modo_cambiado.emit(nuevo_modo)
            self._propagar_modo(nuevo_modo)

    def _propagar_modo(self, modo: ModoPantalla) -> None:
        """Propaga automaticamente el modo a todos los controles hijos con adaptar_modo."""
        for hijo in self.widget_contenido.findChildren(QWidget):
            if hasattr(hijo, "adaptar_modo") and callable(getattr(hijo, "adaptar_modo")):
                try:
                    hijo.adaptar_modo(modo)
                except Exception:
                    pass
