"""Hilo de trabajo en segundo plano para operaciones de IA General (Lens y Modo IA)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from PySide6.QtCore import QThread, Signal

from procesos_ia.aplicacion.servicio_ia_general import ServicioIAGeneral


class HiloIAGeneral(QThread):
    """Ejecuta tareas asincronas de Google Lens y Modo IA sin congelar la interfaz grafica."""

    progreso_actualizado = Signal(int, int, str)
    proceso_completado = Signal(str, object)
    proceso_fallido = Signal(str)
    senial_log = Signal(str)

    def __init__(
        self,
        servicio: ServicioIAGeneral,
        tipo_accion: str,
        parametros: dict[str, Any],
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._servicio = servicio
        self._tipo_accion = tipo_accion
        self._parametros = parametros

    def run(self) -> None:
        """Punto de entrada del hilo que lanza el bucle de eventos asyncio."""
        try:
            asyncio.run(self._ejecutar_accion())
        except Exception as error:
            self.proceso_fallido.emit(str(error))

    async def _ejecutar_accion(self) -> None:
        def notificar_progreso(actual: int, total: int, detalle: str) -> None:
            self.progreso_actualizado.emit(actual, total, detalle)

        def notificar_log(mensaje: str) -> None:
            self.senial_log.emit(mensaje)

        if self._tipo_accion == "imagen_individual":
            fuente = self._parametros.get("fuente", "")
            id_reg = self._parametros.get("id_registro", "img_1")
            ficha = await self._servicio.procesar_imagen_lens(fuente, id_reg, callback_log=notificar_log)
            etq = "OK" if ficha.estado_ia == "EXITOSO" else "ALERTA"
            self.proceso_completado.emit(
                f"[{etq}] Análisis completado ({ficha.estado_ia}): {ficha.negocio or ficha.propietario or 'Sin datos'}",
                ficha,
            )

        elif self._tipo_accion == "carpeta_imagenes":
            carpeta = Path(self._parametros.get("carpeta", ""))
            notificar_log(f"[INFO] Procesando carpeta de imágenes 1 a 1: {carpeta}")
            fichas, ruta_csv = await self._servicio.procesar_carpeta_imagenes_lens(
                carpeta, notificar_progreso, notificar_log
            )
            con_ia = sum(1 for f in fichas if f.estado_ia == "EXITOSO")
            sin_ia = sum(1 for f in fichas if f.estado_ia == "SIN_VISION_GENERAL")
            ruta_abs = str(ruta_csv.resolve())
            self.proceso_completado.emit(
                f"[OK] Procesadas {len(fichas)} imágenes ({con_ia} con IA). Guardado en: {ruta_abs}",
                fichas,
            )

        elif self._tipo_accion == "csv_imagenes":
            ruta_csv = Path(self._parametros.get("ruta_csv", ""))
            columna = self._parametros.get("columna", "")
            notificar_log(f"[INFO] Procesando CSV con imágenes en columna '{columna}': {ruta_csv.name}")
            fichas, salida = await self._servicio.procesar_csv_con_lens(
                ruta_csv, columna, notificar_progreso, notificar_log
            )
            con_ia = sum(1 for f in fichas if f.estado_ia == "EXITOSO")
            ruta_abs = str(salida.resolve())
            notificar_log(f"[OK] CSV enriquecido con {len(fichas)} registros ({con_ia} con respuesta IA).")
            notificar_log(f"[OK] Archivo guardado en: {ruta_abs}")
            self.proceso_completado.emit(
                f"[OK] CSV enriquecido con {len(fichas)} registros. Guardado en: {ruta_abs}",
                fichas,
            )

        elif self._tipo_accion == "modo_ia_lote":
            filas = self._parametros.get("filas", [])
            instrucciones = self._parametros.get("instrucciones", "")
            columnas = self._parametros.get("columnas")
            tamano = int(self._parametros.get("tamano_lote", 5))
            nombre = self._parametros.get("nombre_salida", "evaluacion")
            notificar_log(f"[INFO] Iniciando evaluación en Modo IA con lotes de {tamano}...")
            resultado, ruta_salida = await self._servicio.procesar_modo_ia_lote(
                filas, instrucciones, columnas, tamano, notificar_progreso, notificar_log, nombre
            )
            ruta_abs = str(ruta_salida.resolve()) if ruta_salida else "salida"
            notificar_log(f"[OK] Modo IA completado con {len(resultado)} respuestas.")
            notificar_log(f"[OK] Archivo guardado en: {ruta_abs}")
            self.proceso_completado.emit(
                f"[OK] Modo IA completo con {len(resultado)} respuestas. Guardado en: {ruta_abs}",
                ruta_salida or resultado,
            )
        else:
            self.proceso_fallido.emit(f"[ERROR] Acción no reconocida: {self._tipo_accion}")

    def cancelar(self) -> None:
        """Solicita la cancelacion anticipada del proceso."""
        self._servicio.cancelar()
