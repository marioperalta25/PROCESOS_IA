"""Coordinador central del trabajo, identidad de registros y persistencia WAL."""

from __future__ import annotations

from datetime import datetime, timezone
import time

from procesos_ia.aplicacion.contratos import (
    EscritorWalProtocol,
    LectorFlujoProtocol,
    NotificadorProgresoProtocol,
    ServicioInferenciaProtocol,
    ValidadorSemanticoProtocol,
)
from procesos_ia.dominio.excepciones import (
    ErrorIntegridadWal,
    ErrorProcesamiento,
    ErrorRecuperacionProgreso,
)
from procesos_ia.dominio.modelos import (
    ConfiguracionTrabajo,
    EstadoProcesamiento,
    MetricasProgreso,
    RegistroConfirmado,
    RegistroEntrada,
    TransaccionWal,
)


class CoordinadorTrabajo:
    """Orquesta la lectura, inferencia correlacionada, validación y commits WAL."""

    def __init__(
        self,
        lector: LectorFlujoProtocol,
        escritor_wal: EscritorWalProtocol,
        inferencia: ServicioInferenciaProtocol,
        validador: ValidadorSemanticoProtocol,
        notificador: NotificadorProgresoProtocol,
        configuracion: ConfiguracionTrabajo,
    ) -> None:
        self._lector = lector
        self._escritor_wal = escritor_wal
        self._inferencia = inferencia
        self._validador = validador
        self._notificador = notificador
        self._config = configuracion

        self._estado = EstadoProcesamiento.INACTIVO
        self._ultimo_confirmado = 0
        self._total_estimado = 0
        self._numero_transaccion = 0
        self._confirmados_sesion = 0
        self._errores_sesion = 0
        self._inicio_sesion_segundos = 0.0

    @property
    def estado(self) -> EstadoProcesamiento:
        return self._estado

    @property
    def ultimo_indice_confirmado(self) -> int:
        return self._ultimo_confirmado

    def iniciar_o_reanudar(self) -> int:
        """Inicializa componentes, concilia progreso confirmado e inicia sesión."""
        self._estado = EstadoProcesamiento.PREPARANDO
        self._notificador.notificar_cambio_estado(
            self._estado, "Inicializando origen de datos y bitacora WAL"
        )

        encabezados_origen = self._lector.inicializar(self._config.ruta_entrada)
        self._total_estimado = self._lector.estimar_total_registros()

        # Conciliar esquema total: columnas origen + columnas modelo + control de fallos
        encabezados_totales = list(encabezados_origen)
        for col in self._config.columnas_salida_modelo:
            if col not in encabezados_totales:
                encabezados_totales.append(col)
        for col_ctrl in ("estado_ia", "error_ia"):
            if col_ctrl not in encabezados_totales:
                encabezados_totales.append(col_ctrl)

        self._ultimo_confirmado = self._escritor_wal.inicializar(
            self._config.directorio_salida, encabezados_totales
        )

        if self._ultimo_confirmado < 0:
            raise ErrorRecuperacionProgreso(
                self._ultimo_confirmado, "Cursor de recuperacion invalido"
            )

        # Abrir flujo continuo en el lector para lectura O(1) por fila
        if hasattr(self._lector, "abrir_flujo"):
            self._lector.abrir_flujo(self._ultimo_confirmado)

        self._estado = EstadoProcesamiento.PROCESANDO
        self._inicio_sesion_segundos = time.monotonic()
        self._notificador.notificar_cambio_estado(
            self._estado,
            f"Procesando desde registro confirmado {self._ultimo_confirmado}",
        )
        return self._ultimo_confirmado

    def procesar_siguiente_lote(self) -> bool:
        """Procesa un unico lote con correspondencia estricta por ID y commit WAL."""
        if self._estado != EstadoProcesamiento.PROCESANDO:
            return False

        if hasattr(self._lector, "leer_siguiente_bloque"):
            lote = self._lector.leer_siguiente_bloque(self._config.tamano_lote)
        else:
            generador = self._lector.leer_bloque(
                tamano_bloque=self._config.tamano_lote,
                saltar_hasta_indice=self._ultimo_confirmado,
            )
            lote = list(generador)

        if not lote:
            self._estado = EstadoProcesamiento.COMPLETADO
            self._notificador.notificar_cambio_estado(
                self._estado, "Procesamiento de todos los registros finalizado"
            )
            return False

        # Inferencia desacoplada
        respuestas_crudas = self._inferencia.procesar_lote(lote, self._config)

        # Mapa de respuestas por ID estable para impedir desfasajes por posicion ordinal
        mapa_respuestas = {
            r.get("identificador"): r
            for r in respuestas_crudas
            if isinstance(r, dict) and "identificador" in r
        }

        registros_confirmados: list[RegistroConfirmado] = []
        marca_tiempo = datetime.now(timezone.utc).isoformat()

        for entrada in lote:
            respuesta_cruda = mapa_respuestas.get(entrada.identificador, {})
            resultado = self._validador.validar_respuesta(entrada, respuesta_cruda)

            valores_completos = dict(entrada.valores_originales)
            if resultado.es_valido_sintactico and resultado.es_valido_semantico:
                for clave, valor in resultado.salida_estructurada.items():
                    valores_completos[str(clave)] = str(valor)
                valores_completos["estado_ia"] = "exito"
                valores_completos["error_ia"] = ""
                self._confirmados_sesion += 1
            else:
                for col in self._config.columnas_salida_modelo:
                    if col not in valores_completos:
                        valores_completos[col] = ""
                valores_completos["estado_ia"] = "error"
                motivo = "; ".join(resultado.errores) if resultado.errores else "Respuesta no valida"
                valores_completos["error_ia"] = motivo
                self._errores_sesion += 1

            # Cada fila se preserva en la salida (exito o error) manteniendo correspondencia 1:1
            registros_confirmados.append(
                RegistroConfirmado(
                    identificador=entrada.identificador,
                    indice_fila=entrada.indice_fila,
                    valores_finales=valores_completos,
                    marca_tiempo_utc=marca_tiempo,
                )
            )

        # El avance del cursor solo avanza hasta el ultimo indice consecutivamente confirmado
        indices_confirmados = {r.indice_fila for r in registros_confirmados}
        cursor_avance = self._ultimo_confirmado
        for entrada in lote:
            if entrada.indice_fila in indices_confirmados:
                cursor_avance = entrada.indice_fila
            else:
                break
        ultimo_indice_lote = cursor_avance

        # Persistencia en bitacora WAL antes de confirmar el avance del cursor
        self._numero_transaccion += 1
        transaccion = TransaccionWal(
            numero_transaccion=self._numero_transaccion,
            registros=tuple(registros_confirmados),
            ultimo_indice_confirmado=ultimo_indice_lote,
        )
        self._escritor_wal.registrar_transaccion(transaccion)

        # Confirmacion fisica en disco (fsync)
        nuevo_confirmado = self._escritor_wal.confirmar_checkpoint()
        if nuevo_confirmado < self._ultimo_confirmado:
            raise ErrorIntegridadWal("El puntero de checkpoint retrocedio en disco")

        self._ultimo_confirmado = nuevo_confirmado
        self._emitir_metricas()
        return True

    def pausar(self) -> None:
        """Pausa cooperativa respetando la transaccion confirmada actual."""
        if self._estado == EstadoProcesamiento.PROCESANDO:
            self._estado = EstadoProcesamiento.PAUSADO
            self._notificador.notificar_cambio_estado(
                self._estado, "Procesamiento pausado por el usuario"
            )

    def cancelar(self) -> None:
        """Cancela cooperativamente y libera manejadores abiertos."""
        self._estado = EstadoProcesamiento.CANCELADO
        self._notificador.notificar_cambio_estado(
            self._estado, "Procesamiento cancelado por el usuario"
        )
        self.cerrar()

    def cerrar(self) -> None:
        """Cierre de recursos sin perdida de datos confirmados."""
        self._lector.cerrar()
        self._escritor_wal.cerrar()

    def _emitir_metricas(self) -> None:
        tiempo_transcurrido = max(
            0.001, time.monotonic() - self._inicio_sesion_segundos
        )
        velocidad = self._confirmados_sesion / tiempo_transcurrido
        memoria_mb = self._obtener_memoria_proceso_mb()

        # Telemetria liviana sin acumular historiales pesados (< 10 MB)
        metricas = MetricasProgreso(
            total_estimado=self._total_estimado,
            confirmados=self._confirmados_sesion,
            con_error=self._errores_sesion,
            ultimo_indice_confirmado=self._ultimo_confirmado,
            registros_por_segundo=round(velocidad, 2),
            memoria_usada_mb=memoria_mb,
        )
        self._notificador.notificar_progreso(metricas)

    @staticmethod
    def _obtener_memoria_proceso_mb() -> float:
        try:
            import psutil
            return round(psutil.Process().memory_info().rss / (1024 * 1024), 2)
        except Exception:
            return 0.0
