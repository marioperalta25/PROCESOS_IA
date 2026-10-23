"""Respuesta de chat en segundo plano con cancelación cooperativa."""

from threading import Event
from time import monotonic
from PySide6.QtCore import QThread, Signal


class HiloChat(QThread):
    resultado = Signal(object, str)
    error = Signal(str)
    fragmento = Signal(str, str)

    def __init__(self, servicio, argumentos: tuple, parent=None) -> None:
        super().__init__(parent)
        self._servicio, self._argumentos = servicio, argumentos
        self._cancelacion = Event()
        self._texto = ""
        self._ultima_emision = 0.0

    def _al_fragmento(self, texto: str) -> None:
        if self._cancelacion.is_set():
            return
        self._texto += texto
        ahora = monotonic()
        intervalo = self._servicio.parametros["limites"]["progreso_intervalo_segundos"]
        if ahora - self._ultima_emision >= intervalo:
            self.fragmento.emit(self._argumentos[0]["id"], self._texto)
            self._ultima_emision = ahora

    def cancelar(self) -> None:
        self._cancelacion.set()

    def run(self) -> None:
        datos, entrada, modelo, contexto, temperatura, reintentar = self._argumentos
        try:
            resultado, aviso = self._servicio.responder(
                datos, entrada, modelo, contexto, temperatura, self._cancelacion, reintentar,
                al_fragmento=self._al_fragmento,
            )
            self.resultado.emit(resultado, aviso)
        except Exception as error:
            self.error.emit(str(error))
