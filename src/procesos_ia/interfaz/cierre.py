"""Cierre diferido de ventanas sin interrumpir escrituras ni bloquear Qt."""

from PySide6.QtCore import QObject, QTimer
from shiboken6 import isValid


class CierreCooperativo(QObject):
    """Espera la senial finished de todos los hilos que pertenecen a la ventana."""

    def __init__(self, ventana) -> None:
        super().__init__(ventana)
        self._ventana = ventana
        self.pendiente = False
        self._completado = False
        self._hilos = ()

    def solicitar(self, evento, hilos) -> None:
        activos = tuple(hilo for hilo in hilos if hilo and hilo.isRunning())
        if not activos:
            evento.accept()
            return
        evento.ignore()
        if self.pendiente:
            return
        self.pendiente = True
        self._hilos = activos
        self._ventana.setEnabled(False)
        for hilo in activos:
            hilo.finished.connect(self._al_terminar)
            if hasattr(hilo, "cancelar"):
                hilo.cancelar()
            else:
                hilo.requestInterruption()
        self._al_terminar()

    def _al_terminar(self) -> None:
        QTimer.singleShot(0, self._comprobar)

    def _comprobar(self) -> None:
        if not self._completado and not any(isValid(hilo) and hilo.isRunning() for hilo in self._hilos):
            self._completado = True
            self._ventana.close()
