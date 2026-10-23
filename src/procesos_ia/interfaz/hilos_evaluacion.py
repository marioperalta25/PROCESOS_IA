"""Trabajos acotados de muestra y refinamiento fuera del hilo visual."""

from threading import Event
from PySide6.QtCore import QObject, QThread, Signal

from procesos_ia.aplicacion.muestra import evaluar_muestra
from procesos_ia.aplicacion.contratos import ServicioInferenciaProtocol
from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
from procesos_ia.dominio.modelos import ConfiguracionTrabajo
from procesos_ia.dominio.prompts import PeticionRefinamiento
from procesos_ia.infraestructura.archivos.fabrica_lectores import crear_lector_flujo


class HiloMuestra(QThread):
    senial_resultado = Signal(list)
    senial_error = Signal(str)

    def __init__(
        self, configuracion: ConfiguracionTrabajo, inferencia: ServicioInferenciaProtocol,
        limite: int, parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._configuracion = configuracion
        self._inferencia = inferencia
        self._limite = limite
        self._cancelacion = Event()

    def cancelar(self) -> None:
        self._cancelacion.set()

    def run(self) -> None:
        try:
            lector = crear_lector_flujo(self._configuracion.ruta_entrada)
            filas = evaluar_muestra(
                self._configuracion, lector, self._inferencia, self._limite, self._cancelacion,
            )
            if not self._cancelacion.is_set():
                self.senial_resultado.emit(filas)
        except Exception as error:
            self.senial_error.emit(str(error))


class HiloRefinamiento(QThread):
    senial_resultado = Signal(object)
    senial_error = Signal(str)

    def __init__(
        self, servicio: ServicioCatalogoPrompts, peticion: PeticionRefinamiento,
        modelo: str, parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._servicio = servicio
        self._peticion = peticion
        self._modelo = modelo

    def run(self) -> None:
        try:
            self.senial_resultado.emit(self._servicio.refinar_idea(self._peticion, self._modelo))
        except Exception as error:
            self.senial_error.emit(str(error))
