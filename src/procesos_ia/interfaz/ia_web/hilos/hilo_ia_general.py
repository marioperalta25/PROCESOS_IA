"""Hilo de trabajo en segundo plano para operaciones de IA General (Lens y Modo IA)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from procesos_ia.dominio.excepciones import ErrorPersistenciaTabular
from PySide6.QtCore import QThread, Signal

from procesos_ia.aplicacion.ia_web.visual_1a1.servicio_ia_general import ServicioIAGeneral


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
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tarea_principal: asyncio.Task[Any] | None = None

    def run(self) -> None:
        """Punto de entrada del hilo que lanza el bucle de eventos asyncio."""
        try:
            asyncio.run(self._ejecutar_accion())
        except asyncio.CancelledError:
            self.senial_log.emit("[INFO] Hilo IA General detenido por cancelacion del usuario.")
        except Exception as error:
            if getattr(self._servicio, "_cancelado", False) and not isinstance(error, (ErrorPersistenciaTabular, ValueError)):
                self.senial_log.emit("[INFO] Hilo IA General detenido por cancelacion del usuario.")
            else:
                self.proceso_fallido.emit("\n".join([str(error), *getattr(error, "__notes__", ())]))

    async def _ejecutar_accion(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._tarea_principal = asyncio.current_task()
        def notificar_progreso(actual: int, total: int, detalle: str) -> None:
            self.progreso_actualizado.emit(actual, total, detalle)

        def notificar_log(mensaje: str) -> None:
            self.senial_log.emit(mensaje)

        gen_md = bool(self._parametros.get("generar_auditoria_md", True))
        if self._tipo_accion == "imagen_individual":
            fuente = self._parametros.get("fuente", "")
            id_reg = self._parametros.get("id_registro", "img_1")
            c_sal = Path(self._parametros["carpeta_salida"]) if self._parametros.get("carpeta_salida") else None
            ficha, ruta_csv = await self._servicio.procesar_url_individual(
                fuente, id_reg, carpeta_salida=c_sal, callback_log=notificar_log,
                generar_auditoria_md=gen_md,
            )
            etq = "OK" if ficha.estado_ia == "EXITOSO" else "ALERTA"
            msg_salida = f" Guardado en: {ruta_csv.resolve()}" if ruta_csv else ""
            self.proceso_completado.emit(
                f"[{etq}] Análisis completado ({ficha.estado_ia}): {ficha.negocio or ficha.propietario or 'Sin datos'}.{msg_salida}",
                ficha,
            )

        elif self._tipo_accion == "carpeta_imagenes":
            carpeta = Path(self._parametros.get("carpeta", ""))
            archivos = self._parametros.get("archivos")
            modo = self._parametros.get("modo_escritura", "sobrescribir")
            csv_previo = self._parametros.get("csv_existente")
            c_sal = Path(self._parametros["carpeta_salida"]) if self._parametros.get("carpeta_salida") else None
            notificar_log(f"[INFO] Procesando carpeta de imágenes: {carpeta}")
            fichas, ruta_csv = await self._servicio.procesar_carpeta_imagenes_lens(
                carpeta, notificar_progreso, notificar_log,
                archivos_especificos=archivos,
                modo_escritura=modo,
                csv_existente=csv_previo,
                carpeta_salida=c_sal,
                generar_auditoria_md=gen_md,
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
            nombre_hoja = self._parametros.get("nombre_hoja")
            c_sal = Path(self._parametros["carpeta_salida"]) if self._parametros.get("carpeta_salida") else None
            sal_ext = self._parametros.get("salida_existente")
            filas_pre = self._parametros.get("filas_precargadas")
            notificar_log(f"[INFO] Procesando archivo con imágenes en columna '{columna}': {ruta_csv.name}")
            fichas, salida = await self._servicio.procesar_csv_con_lens(
                ruta_csv, columna, callback_progreso=notificar_progreso, callback_log=notificar_log, carpeta_salida=c_sal,
                generar_auditoria_md=gen_md, nombre_hoja=nombre_hoja,
                salida_existente=sal_ext, filas_precargadas=filas_pre,
                trabajo_tabular=self._parametros.get("trabajo_tabular"),
            )
            con_ia = sum(1 for f in fichas if f.estado_ia == "EXITOSO")
            ruta_abs = str(salida.resolve())
            notificar_log(f"[OK] Archivo enriquecido con {len(fichas)} registros ({con_ia} con respuesta IA).")
            notificar_log(f"[OK] Guardado en: {ruta_abs}")
            self.proceso_completado.emit(
                f"[OK] Archivo enriquecido con {len(fichas)} registros. Guardado en: {ruta_abs}",
                fichas,
            )

        elif self._tipo_accion == "modo_ia_lote":
            filas = self._parametros.get("filas", [])
            instrucciones = self._parametros.get("instrucciones", "")
            columnas = self._parametros.get("columnas")
            tamano = int(self._parametros.get("tamano_lote", 5))
            lotes_conv = int(self._parametros.get("lotes_por_conversacion", 5))
            nombre = self._parametros.get("nombre_salida", "evaluacion")
            salida_ext = self._parametros.get("salida_existente")
            notificar_log(f"[INFO] Iniciando evaluación en Modo IA con lotes de {tamano} ({lotes_conv} lotes/chat)...")
            resultado, ruta_salida = await self._servicio.procesar_modo_ia_lote(
                filas, instrucciones, columnas, tamano, lotes_conv, notificar_progreso, notificar_log, nombre,
                carpeta_salida=self._parametros.get("carpeta_salida"),
                generar_auditoria_md=gen_md,
                salida_existente=salida_ext,
                trabajo_tabular=self._parametros.get("trabajo_tabular"),
            )
            ruta_abs = str(ruta_salida.resolve()) if ruta_salida else "salida"
            from procesos_ia.aplicacion.comun.identidad_tabular import parametros_tabulares
            etiqueta = "cancelado" if getattr(self._servicio, "_cancelado", False) else "completado"
            parametros = parametros_tabulares()
            mensaje = parametros[etiqueta].format(cantidad=len(resultado))
            estados = self._servicio.enrutador.gestor_procesos().configuracion["estados"]
            if ruta_salida and ruta_salida.parent.parent.name == estados["fallidos"]:
                mensaje = parametros["parcial"]
            notificar_log(mensaje)
            notificar_log(f"[OK] Archivo guardado en: {ruta_abs}")
            self.proceso_completado.emit(
                mensaje,
                ruta_salida or resultado,
            )

        elif self._tipo_accion == "modo_ia_imagenes":
            carpeta = Path(self._parametros.get("carpeta", ""))
            campos = self._parametros.get("campos_activos", [])
            extra = self._parametros.get("instrucciones_extra", "")
            rotacion = int(self._parametros.get("rotacion_chat", 3))
            c_sal = Path(self._parametros["carpeta_salida"]) if self._parametros.get("carpeta_salida") else None
            archivos, modo = self._parametros.get("archivos"), self._parametros.get("modo_escritura", "sobrescribir")
            csv_previo = self._parametros.get("csv_existente")
            notificar_log(f"[INFO] Iniciando Modo IA Imágenes: {carpeta.name} (rotación {rotacion} imgs/chat)...")
            resultado, ruta_salida = await self._servicio.procesar_modo_ia_imagenes(
                carpeta=carpeta,
                campos_activos=campos,
                instrucciones_adicionales=extra,
                rotacion_chat=rotacion,
                callback_progreso=notificar_progreso,
                callback_log=notificar_log,
                carpeta_salida=c_sal,
                generar_auditoria_md=gen_md,
                archivos_especificos=archivos,
                modo_escritura=modo,
                csv_existente=csv_previo,
            )
            ruta_abs = str(ruta_salida.resolve()) if ruta_salida else "salida"
            notificar_log(f"[OK] Modo IA Imágenes finalizado ({len(resultado)} registros). Guardado en: {ruta_abs}")
            self.proceso_completado.emit(
                f"[OK] Modo IA Imágenes finalizado ({len(resultado)} registros). Guardado en: {ruta_abs}",
                resultado,
            )
        elif self._tipo_accion == "modo_ia_urls":
            p = self._parametros
            notificar_log(f"[INFO] Iniciando Modo IA por URLs: lotes de {p.get('tamano_lote', 3)}...")
            resultado, ruta_salida = await self._servicio.procesar_modo_ia_urls(
                filas=p.get("filas", []), columna_url=p.get("columna", ""),
                campos_activos=p.get("campos_activos", []), instrucciones_adicionales=p.get("instrucciones_extra", ""),
                tamano_lote=int(p.get("tamano_lote", 3)), lotes_por_conversacion=int(p.get("lotes_por_conversacion", 4)),
                nombre_salida=p.get("nombre_salida", "urls_modo_ia"), carpeta_salida=p.get("carpeta_salida"),
                callback_progreso=notificar_progreso, callback_log=notificar_log,
                generar_auditoria_md=gen_md, trabajo_tabular=p.get("trabajo_tabular"),
            )
            ruta_abs = str(ruta_salida.resolve()) if ruta_salida else "salida"
            msg = f"[OK] Modo IA URLs finalizado ({len(resultado)} registros). Guardado en: {ruta_abs}"
            notificar_log(msg); self.proceso_completado.emit(msg, ruta_salida or resultado)
        else:
            self.proceso_fallido.emit(f"[ERROR] Acción no reconocida: {self._tipo_accion}")

    def cancelar(self) -> None:
        """Solicita la cancelacion anticipada, interrumpe asyncio y cierra el navegador."""
        self._servicio.cancelar()
        if self._loop is not None and self._tarea_principal is not None and not self._loop.is_closed():
            try:
                self._loop.call_soon_threadsafe(self._tarea_principal.cancel)
            except RuntimeError:
                pass
        self._servicio.forzar_cierre_inmediato()
