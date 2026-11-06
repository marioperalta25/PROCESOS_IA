"""Hilo de ejecucion en segundo plano para procesamiento masivo en DeepSeek y Gemini."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from PySide6.QtCore import QThread, Signal

from procesos_ia.aplicacion.ia_web.motores.procesador_imagenes_motores import (
    ProcesadorImagenesMotores,
)
from procesos_ia.aplicacion.ia_web.motores.servicio_procesamiento_web import ServicioProcesamientoWeb


class HiloProcesamientoWeb(QThread):
    """Ejecuta peticiones por lotes e imagenes en Gemini y DeepSeek sin bloquear la UI."""

    progreso_actualizado = Signal(int, int, str)
    proceso_completado = Signal(str, object)
    proceso_fallido = Signal(str)
    senial_log = Signal(str)

    def __init__(
        self,
        servicio: ServicioProcesamientoWeb,
        motor: str,
        ruta_csv: Path | None = None,
        columnas: list[str] | None = None,
        instrucciones: str = "",
        tamano_lote: int = 5,
        columna_imagen: str | None = None,
        carpeta_imagenes: Path | None = None,
        rotacion_chat: int = 2,
        tipo_operacion: str = "csv",
        ruta_directa: Path | None = None,
        campos_activos: list[str] | dict[str, bool] | None = None,
        archivos_especificos: list[Path] | None = None,
        modo_escritura: str = "sobrescribir",
        csv_existente: Path | None = None,
        carpeta_salida: Path | None = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._servicio = servicio
        self._motor = motor
        self._ruta_csv = ruta_csv
        self._columnas = columnas or []
        self._instrucciones = instrucciones
        self._tamano_lote = tamano_lote
        self._columna_imagen = columna_imagen
        self._carpeta_imagenes = carpeta_imagenes
        self._rotacion_chat = rotacion_chat
        self._tipo_operacion = tipo_operacion
        self._ruta_directa = ruta_directa
        self._campos_activos = campos_activos or ["negocio", "telefonos"]
        self._archivos_especificos = archivos_especificos
        self._modo_escritura = modo_escritura
        self._csv_existente = csv_existente
        self._carpeta_salida = carpeta_salida
        self._cancelado = False

    def run(self) -> None:
        """Punto de entrada del hilo que lanza la corrutina asincrona."""
        try:
            asyncio.run(self._ejecutar())
        except Exception as error:
            self.proceso_fallido.emit("\n".join([str(error), *getattr(error, "__notes__", ())]))

    async def _ejecutar(self) -> None:
        def on_progreso(act: int, tot: int, det: str) -> None:
            self.progreso_actualizado.emit(act, tot, det)

        def on_log(msg: str) -> None:
            self.senial_log.emit(msg)

        if self._tipo_operacion == "extraccion_negocios_imagenes" and self._ruta_directa:
            proc_img = ProcesadorImagenesMotores(
                self._servicio._gestor, self._servicio._enrutador, self._servicio._config
            )
            resultados, ruta_salida = await proc_img.ejecutar(
                motor=self._motor,
                carpeta=self._ruta_directa,
                campos_activos=self._campos_activos,
                instrucciones_adicionales=self._instrucciones,
                rotacion_chat=self._rotacion_chat,
                callback_progreso=on_progreso,
                callback_log=on_log,
                carpeta_salida=self._carpeta_salida,
                verificador_cancelacion=lambda: self._cancelado,
                archivos_especificos=self._archivos_especificos,
                modo_escritura=self._modo_escritura,
                csv_existente=self._csv_existente,
            )
        elif self._tipo_operacion == "carpeta_imagenes" and self._ruta_directa:
            resultados, ruta_salida = await self._servicio.procesar_carpeta_imagenes(
                motor=self._motor,
                carpeta=self._ruta_directa,
                instrucciones=self._instrucciones,
                rotacion_chat=self._rotacion_chat,
                callback_progreso=on_progreso,
                callback_log=on_log,
            )
        elif self._tipo_operacion == "imagen_individual" and self._ruta_directa:
            resultados, ruta_salida = await self._servicio.procesar_imagen_individual(
                motor=self._motor,
                ruta_img=self._ruta_directa,
                instrucciones=self._instrucciones,
                callback_progreso=on_progreso,
                callback_log=on_log,
            )
        else:
            if not self._ruta_csv:
                raise ValueError("Se requiere una ruta CSV para el procesamiento tabular.")
            resultados, ruta_salida = await self._servicio.procesar_csv(
                motor=self._motor,
                ruta_csv=self._ruta_csv,
                columnas=self._columnas,
                instrucciones=self._instrucciones,
                tamano_lote=self._tamano_lote,
                columna_imagen=self._columna_imagen,
                carpeta_imagenes=self._carpeta_imagenes,
                rotacion_chat=self._rotacion_chat,
                callback_progreso=on_progreso,
                callback_log=on_log,
            )

        self.proceso_completado.emit(
            f"[OK] Procesamiento en {self._motor.upper()} finalizado. {len(resultados)} registros guardados en {ruta_salida.name}",
            ruta_salida,
        )

    def cancelar(self) -> None:
        self._cancelado = True
        self._servicio.cancelar()
