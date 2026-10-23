"""Hilos de trabajo en segundo plano para operaciones no bloqueantes."""

from __future__ import annotations

from threading import Event
from typing import Any
from PySide6.QtCore import QMutex, QObject, QThread, QWaitCondition, Signal

from procesos_ia.aplicacion.contratos import (
    EscritorWalProtocol,
    LectorFlujoProtocol,
    NotificadorProgresoProtocol,
    ServicioInferenciaProtocol,
    ValidadorSemanticoProtocol,
)
from procesos_ia.aplicacion.coordinador import CoordinadorTrabajo
from procesos_ia.dominio.excepciones import ErrorConexionRechazada, ErrorProcesamiento
from procesos_ia.dominio.modelos import (
    ConfiguracionTrabajo,
    EstadoProcesamiento,
    MetricasProgreso,
)
from procesos_ia.dominio.validador import ValidadorSemantico
from procesos_ia.infraestructura.archivos.fabrica_lectores import crear_lector_flujo
from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.ollama.modelos import (
    DiagnosticoOllama,
    InformacionModelo,
)
from procesos_ia.infraestructura.ollama.servicio_inferencia import (
    ServicioInferenciaOllama,
)
from procesos_ia.infraestructura.persistencia.escritor_wal import EscritorWal


class HiloListarModelos(QThread):
    """Consulta modelos instalados (/api/tags) y levanta el servidor si esta detenido."""

    senial_modelos = Signal(list)
    senial_mensaje = Signal(str)
    senial_error = Signal(str)

    def __init__(
        self,
        cliente_http: ClienteHttpOllama | None = None,
        auto_iniciar: bool = False,
        tiempo_limite: float = 3.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._cliente = cliente_http or ClienteHttpOllama()
        self._auto_iniciar = auto_iniciar
        self._cancelacion = Event()
        self._tiempo_limite = tiempo_limite

    def cancelar(self) -> None:
        """Solicita abandonar la consulta o espera de arranque en el siguiente limite."""
        self._cancelacion.set()

    def run(self) -> None:
        try:
            if self._cancelacion.is_set():
                return
            # 1. Intentar consulta rapida inicial si el servidor ya esta corriendo
            try:
                modelos = self._cliente.listar_modelos(tiempo_limite=1.5, reintentos=0)
                self.senial_modelos.emit(modelos)
                return
            except ErrorConexionRechazada:
                if not self._auto_iniciar or not self._cliente.es_ejecutable_disponible():
                    raise

            # 2. Si esta detenido pero instalado, encender servidor local
            self.senial_mensaje.emit("[INFO] Servicio Ollama detenido. Levantando servidor local...")
            if self._cancelacion.is_set():
                return
            iniciado = self._cliente.iniciar_servicio(
                tiempo_espera=6.0, cancelacion=self._cancelacion,
            )
            if self._cancelacion.is_set():
                return
            if not iniciado:
                raise ErrorProcesamiento("No se pudo iniciar el servicio de Ollama automaticamente.")

            self.senial_mensaje.emit("[OK] Servidor Ollama iniciado exitosamente. Consultando modelos...")
            modelos = self._cliente.listar_modelos(tiempo_limite=self._tiempo_limite, reintentos=0)
            self.senial_modelos.emit(modelos)
        except Exception as error:
            self.senial_error.emit(str(error))


class HiloDiagnosticoOllama(QThread):
    """Consulta en segundo plano el estado de Ollama y la lista de modelos disponibles."""

    senial_diagnostico = Signal(object, list)
    senial_error = Signal(str)

    def __init__(
        self,
        cliente_http: ClienteHttpOllama | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._cliente = cliente_http or ClienteHttpOllama()

    def run(self) -> None:
        try:
            diag = self._cliente.verificar_estado()
            modelos: list[InformacionModelo] = []
            if diag.estado.value == "disponible":
                modelos = self._cliente.listar_modelos(tiempo_limite=3.0, reintentos=0)
            self.senial_diagnostico.emit(diag, modelos)
        except Exception as error:
            self.senial_error.emit(str(error))


class HiloLiberarMemoria(QThread):
    """Descarga el modelo de la VRAM/RAM en segundo plano para cuidar el hardware."""

    senial_resultado = Signal(bool, str)

    def __init__(
        self,
        modelo: str,
        cliente_http: ClienteHttpOllama | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._modelo = modelo
        self._cliente = cliente_http or ClienteHttpOllama()

    def run(self) -> None:
        try:
            ok = self._cliente.liberar_memoria_modelo(self._modelo)
            msg = (
                f"[OK] Memoria de '{self._modelo}' liberada exitosamente"
                if ok
                else f"[ALERTA] No se pudo descargar '{self._modelo}' de memoria"
            )
            self.senial_resultado.emit(ok, msg)
        except Exception as err:
            self.senial_resultado.emit(False, f"[ERROR] Fallo al liberar memoria: {err}")


class NotificadorProgresoQt(NotificadorProgresoProtocol):
    """Adaptador que implementa NotificadorProgresoProtocol y despacha a señales de Qt."""

    def __init__(self, hilo: HiloCoordinadorTrabajo) -> None:
        self._hilo = hilo

    def notificar_progreso(self, metricas: MetricasProgreso) -> None:
        self._hilo.senial_progreso.emit(
            metricas.ultimo_indice_confirmado,
            metricas.total_estimado,
            metricas.memoria_usada_mb,
            metricas.registros_por_segundo,
        )

    def notificar_cambio_estado(
        self,
        estado: EstadoProcesamiento,
        mensaje: str,
    ) -> None:
        self._hilo.senial_fase_cambiada.emit(f"[{estado.value.upper()}]")
        self._hilo.senial_mensaje.emit(f"[INFO] {mensaje}")


class HiloCoordinadorTrabajo(QThread):
    """Ejecuta el procesamiento masivo sin bloquear la interfaz gráfica."""

    senial_progreso = Signal(int, int, float, float)  # fila, total, ram_mb, filas_por_seg
    senial_fase_cambiada = Signal(str)  # [EN PROCESO], [PAUSADO], [COMPLETADO], etc.
    senial_mensaje = Signal(str)
    senial_finalizado = Signal(bool, str)
    senial_error = Signal(str)

    def __init__(
        self,
        configuracion: ConfiguracionTrabajo,
        coordinador: CoordinadorTrabajo | None = None,
        servicio_inferencia: ServicioInferenciaProtocol | None = None,
        lector: LectorFlujoProtocol | None = None,
        escritor_wal: EscritorWalProtocol | None = None,
        validador: ValidadorSemanticoProtocol | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._configuracion = configuracion
        self._cancelado = False
        self._pausado = False
        self._mutex = QMutex()
        self._condicion_pausa = QWaitCondition()

        if coordinador is not None:
            self._coordinador = coordinador
        else:
            notificador = NotificadorProgresoQt(self)
            lec = lector or crear_lector_flujo(configuracion.ruta_entrada)
            esc = escritor_wal or EscritorWal(
                limite_filas_particion=configuracion.limite_filas_particion
            )
            inf = servicio_inferencia or ServicioInferenciaOllama()
            val = validador or ValidadorSemantico(
                contrato=configuracion.obtener_contrato()
            )
            self._coordinador = CoordinadorTrabajo(
                lector=lec,
                escritor_wal=esc,
                inferencia=inf,
                validador=val,
                notificador=notificador,
                configuracion=configuracion,
            )

    def pausar(self) -> None:
        self._mutex.lock()
        self._pausado = True
        self._mutex.unlock()
        self.senial_fase_cambiada.emit("[PAUSADO]")
        self.senial_mensaje.emit("[INFO] Procesamiento pausado por el usuario")

    def reanudar(self) -> None:
        self._mutex.lock()
        self._pausado = False
        self._condicion_pausa.wakeAll()
        self._mutex.unlock()
        self.senial_fase_cambiada.emit("[PROCESANDO]")
        self.senial_mensaje.emit("[INFO] Procesamiento reanudado")

    def cancelar(self) -> None:
        self._mutex.lock()
        self._cancelado = True
        self._pausado = False
        self._condicion_pausa.wakeAll()
        self._mutex.unlock()
        self.senial_fase_cambiada.emit("[CANCELANDO]")
        self.senial_mensaje.emit("[ALERTA] Solicitud de cancelacion recibida")

    def run(self) -> None:
        try:
            self._coordinador.iniciar_o_reanudar()

            while not self._cancelado:
                self._mutex.lock()
                while self._pausado and not self._cancelado:
                    self._condicion_pausa.wait(self._mutex)
                cancelado = self._cancelado
                self._mutex.unlock()

                if cancelado:
                    break

                hay_mas = self._coordinador.procesar_siguiente_lote()
                if not hay_mas:
                    break

            if self._cancelado:
                self._coordinador.cancelar()
                self.senial_fase_cambiada.emit("[CANCELADO]")
                self.senial_finalizado.emit(
                    False, "[ALERTA] Procesamiento cancelado por el usuario"
                )
            else:
                self.senial_fase_cambiada.emit("[COMPLETADO]")
                self.senial_finalizado.emit(
                    True, "[OK] Procesamiento finalizado y confirmado en disco"
                )

        except Exception as error:
            self.senial_fase_cambiada.emit("[ERROR]")
            self.senial_error.emit(f"[ERROR] Fallo en la ejecucion: {error}")
        finally:
            self._coordinador.cerrar()
