"""Hilos de trabajo en segundo plano para operaciones no bloqueantes."""

from __future__ import annotations

import time
from typing import Any
from PySide6.QtCore import QMutex, QObject, QThread, QWaitCondition, Signal

from procesos_ia.aplicacion.coordinador import CoordinadorTrabajo
from procesos_ia.dominio.modelos import ConfiguracionTrabajo, EstadoProgreso
from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.ollama.modelos import (
    DiagnosticoOllama,
    InformacionModelo,
)


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
                modelos = self._cliente.listar_modelos()
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


class HiloCoordinadorTrabajo(QThread):
    """Ejecuta el procesamiento masivo sin bloquear la interfaz gráfica."""

    senial_progreso = Signal(int, int, float, float)  # fila, total, ram_mb, filas_por_seg
    senial_fase_cambiada = Signal(str)  # [EN PROCESO], [PAUSADO], [COMPLETADO], etc.
    senial_mensaje = Signal(str)
    senial_finalizado = Signal(bool, str)
    senial_error = Signal(str)

    def __init__(
        self,
        coordinador: CoordinadorTrabajo,
        configuracion: ConfiguracionTrabajo,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._coordinador = coordinador
        self._configuracion = configuracion
        self._cancelado = False
        self._pausado = False
        self._mutex = QMutex()
        self._condicion_pausa = QWaitCondition()

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
        self.senial_fase_cambiada.emit("[EN PROCESO]")
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
        self.senial_fase_cambiada.emit("[EN PROCESO]")
        self.senial_mensaje.emit(
            f"[INFO] Iniciando procesamiento de '{self._configuracion.ruta_entrada.name}'..."
        )

        ultimo_tiempo = time.perf_counter()
        filas_procesadas_prev = 0

        def callback_progreso(estado: EstadoProgreso) -> None:
            nonlocal ultimo_tiempo, filas_procesadas_prev

            # Manejo cooperativo de pausa
            self._mutex.lock()
            while self._pausado and not self._cancelado:
                self._condicion_pausa.wait(self._mutex)
            cancelado_actual = self._cancelado
            self._mutex.unlock()

            if cancelado_actual:
                return

            ahora = time.perf_counter()
            delta_t = ahora - ultimo_tiempo
            delta_filas = estado.filas_procesadas - filas_procesadas_prev
            velocidad = (delta_filas / delta_t) if delta_t > 0 else 0.0

            ultimo_tiempo = ahora
            filas_procesadas_prev = estado.filas_procesadas

            self.senial_progreso.emit(
                estado.filas_procesadas,
                estado.filas_totales_estimadas,
                estado.uso_memoria_mb,
                velocidad,
            )

        try:
            resumen = self._coordinador.ejecutar_trabajo(
                configuracion=self._configuracion,
                callback_progreso=callback_progreso,
            )

            if self._cancelado:
                self.senial_fase_cambiada.emit("[CANCELADO]")
                self.senial_finalizado.emit(False, "[ALERTA] Proceso cancelado por el usuario")
            else:
                self.senial_fase_cambiada.emit("[COMPLETADO]")
                msg = (
                    f"[OK] Trabajo finalizado: {resumen.total_procesados} registros "
                    f"({resumen.exitosos} exitosos, {resumen.fallidos} con fallas) "
                    f"en {resumen.duracion_segundos:.2f}s"
                )
                self.senial_finalizado.emit(True, msg)

        except Exception as error:
            self.senial_fase_cambiada.emit("[ERROR]")
            self.senial_error.emit(f"[ERROR] Fallo en la ejecucion: {error}")
