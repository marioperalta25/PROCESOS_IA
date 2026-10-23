"""Módulo para protección antirebote de botones y notificación visual de acciones."""

from __future__ import annotations

from typing import Callable
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QPushButton


_NOTIFICADOR_PREDETERMINADO: Callable[[str], None] | None = None


def establecer_notificador_predeterminado(notificador: Callable[[str], None] | None) -> None:
    """Configura el notificador predeterminado para todos los botones protegidos."""
    global _NOTIFICADOR_PREDETERMINADO
    _NOTIFICADOR_PREDETERMINADO = notificador


def obtener_notificador_predeterminado() -> Callable[[str], None] | None:
    """Devuelve el notificador predeterminado actual."""
    return _NOTIFICADOR_PREDETERMINADO


class ProtectorBotones(QObject):
    """Evita pulsaciones múltiples (doble clic / spam) y notifica el inicio de cada acción."""

    def __init__(
        self,
        notificador_global: Callable[[str], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._notificador = notificador_global
        self._en_enfriamiento: set[int] = set()

    def vincular(
        self,
        boton: QPushButton,
        accion: Callable[[], None],
        mensaje_notificacion: str | None = None,
        notificador: Callable[[str], None] | None = None,
        tiempo_bloqueo_ms: int = 600,
    ) -> None:
        """Conecta un botón con guarda antirebote y notificación inmediata de la acción iniciada."""

        def slot_protegido() -> None:
            btn_id = id(boton)
            if btn_id in self._en_enfriamiento:
                return

            self._en_enfriamiento.add(btn_id)
            boton.setEnabled(False)

            notif = notificador or self._notificador or _NOTIFICADOR_PREDETERMINADO
            if mensaje_notificacion and notif:
                try:
                    notif(mensaje_notificacion)
                except Exception:
                    pass

            try:
                accion()
            finally:
                if tiempo_bloqueo_ms > 0:
                    QTimer.singleShot(
                        tiempo_bloqueo_ms,
                        lambda: self._desbloquear(boton, btn_id),
                    )

        boton.clicked.connect(slot_protegido)

    def _desbloquear(self, boton: QPushButton, btn_id: int) -> None:
        self._en_enfriamiento.discard(btn_id)
        try:
            # Solo reactiva si el botón sigue existiendo en el árbol de Qt
            boton.setEnabled(True)
        except RuntimeError:
            pass


def conectar_boton_protegido(
    boton: QPushButton,
    accion: Callable[[], None],
    mensaje_notificacion: str | None = None,
    notificador: Callable[[str], None] | None = None,
    tiempo_bloqueo_ms: int = 600,
) -> None:
    """Función de conveniencia para proteger un botón individual contra doble clic."""
    protector = getattr(boton, "_protector_instancia", None)
    if protector is None:
        protector = ProtectorBotones(parent=boton)
        setattr(boton, "_protector_instancia", protector)
    protector.vincular(
        boton=boton,
        accion=accion,
        mensaje_notificacion=mensaje_notificacion,
        notificador=notificador,
        tiempo_bloqueo_ms=tiempo_bloqueo_ms,
    )
