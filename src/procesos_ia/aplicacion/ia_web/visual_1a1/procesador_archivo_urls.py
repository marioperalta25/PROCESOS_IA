"""Modulo de aplicacion para procesamiento por lotes de archivos tabulares (CSV y Excel) con URLs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.comun.identidad_tabular import IdentidadTabular
from procesos_ia.aplicacion.comun.trabajo_tabular import TrabajoTabular
from procesos_ia.aplicacion.comun.gestor_reanudacion_base import COLUMNA_ID
from procesos_ia.aplicacion.ia_web.comun.guardador_extracciones import (
    guardar_auditoria_extraccion_md,
    guardar_filas_enriquecidas_csv,
)
from procesos_ia.dominio.reanudacion import EstadoIA
from procesos_ia.dominio.ia_web.desglosador_telefonos import desglosar_ficha_por_telefono
from procesos_ia.dominio.ia_web.ficha_negocio import FichaNegocioLens
from procesos_ia.infraestructura.archivos.fabrica_lectores import crear_lector_flujo
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver


def leer_filas_archivo_tabular(
    ruta_archivo: Path, nombre_hoja: str | None = None
) -> list[dict[str, Any]]:
    """Lee registros en formato diccionario desde archivos CSV o Excel en la hoja indicada."""
    lector = crear_lector_flujo(ruta_archivo, nombre_hoja_excel=nombre_hoja)
    lector.inicializar(ruta_archivo)
    lector.abrir_flujo(saltar_hasta_indice=0)
    filas: list[dict[str, Any]] = []
    try:
        while True:
            bloque = lector.leer_siguiente_bloque(tamano_bloque=500)
            if not bloque:
                break
            for reg in bloque:
                filas.append(dict(reg.valores_originales))
    finally:
        lector.cerrar()
    return filas


class ProcesadorArchivoUrls:
    """Enriquece filas de archivos CSV y Excel procesando imagenes y URLs con Google Lens."""

    def __init__(
        self,
        gestor_sesion: GestorSesionNodriver,
        enrutador: EnrutadorSalidas,
        configuracion: ConfiguracionWeb,
        ejecutor_lens: Callable[..., Any],
    ) -> None:
        self._gestor = gestor_sesion
        self._enrutador = enrutador
        self._config = configuracion
        self._ejecutor_lens = ejecutor_lens

    async def ejecutar(
        self,
        ruta_archivo: Path,
        columna_imagen: str,
        nombre_hoja: str | None = None,
        carpeta_salida: Path | None = None,
        callback_progreso: Callable[[int, int, str], None] | None = None,
        callback_log: Callable[[str], None] | None = None,
        verificador_cancelacion: Callable[[], bool] | None = None,
        generar_auditoria_md: bool = True,
        salida_existente: Any | None = None,
        filas_precargadas: list[dict[str, Any]] | None = None,
        trabajo_tabular: TrabajoTabular | None = None,
    ) -> tuple[list[FichaNegocioLens], Path]:
        """Procesa registros del archivo tabular enriqueciendolos con datos de Google Lens."""
        t_inicio = asyncio.get_running_loop().time()
        filas = trabajo_tabular.filas_pendientes if trabajo_tabular else (
            filas_precargadas if filas_precargadas is not None
            else leer_filas_archivo_tabular(ruta_archivo, nombre_hoja=nombre_hoja)
        )
        trabajo = trabajo_tabular or TrabajoTabular(
            filas, IdentidadTabular.crear(ruta_archivo, "imagenes", filas, "", [columna_imagen],
                                        {"hoja": nombre_hoja, "columna_imagen": columna_imagen}),
        )
        filas = trabajo.filas_pendientes
        total = len(filas)
        resultados: list[FichaNegocioLens] = []
        with trabajo.abrir(
            self._enrutador, f"enriquecido_lens_{ruta_archivo.stem}.csv", carpeta_salida, salida_existente,
        ) as salida:
            if trabajo.solo_exportar:
                if callback_log:
                    callback_log("[INFO] Exportando resultados previos sin abrir el navegador.")
                return [], trabajo.finalizar("completados", guardar_filas_enriquecidas_csv)
            ruta_salida = salida.ruta
            if trabajo.respaldo:
                trabajo.notificar_progreso(callback_progreso, 0, trabajo.parametros["progreso_recuperado"])
            if callback_log:
                hoja_txt = f" (Hoja: {nombre_hoja})" if nombre_hoja else ""
                callback_log(f"[INFO] Procesando archivo{hoja_txt} con {total} registros en columna '{columna_imagen}': {ruta_archivo.name}")
                if total == 0:
                    callback_log("[ALERTA] No hay registros pendientes para procesar; no se abrira el navegador.")
                elif all(not str(f.get(columna_imagen, "") or "").strip() for f in filas):
                    callback_log(f"[ALERTA] Todos los registros tienen vacia la columna '{columna_imagen}'; no se abrira el navegador.")

            try:
                for idx, fila in enumerate(filas, start=1):
                    if verificador_cancelacion and verificador_cancelacion():
                        if callback_log:
                            callback_log("[INFO] Procesamiento de archivo cancelado por el usuario.")
                        break

                    valor_img = str(fila.get(columna_imagen, "") or "").strip()
                    if callback_log:
                        callback_log(f"[INFO] ({idx}/{total}) Analizando: {valor_img or '(vacio)'}")

                    try:
                        tiempo_max = max(float(self._config.tiempo_espera_respuesta_segundos) + 8.0, 20.0)
                        ficha = (
                            await asyncio.wait_for(
                                self._ejecutor_lens(
                                    fuente_imagen=valor_img,
                                    id_registro=fila[COLUMNA_ID],
                                    cerrar_pestana=True,
                                    callback_log=callback_log,
                                ),
                                timeout=tiempo_max,
                            )
                            if valor_img
                            else FichaNegocioLens(id_registro=fila[COLUMNA_ID], texto_sintesis="[INFO] Sin imagen")
                        )
                    except asyncio.TimeoutError:
                        if callback_log:
                            callback_log(f"[ALERTA] Tiempo agotado en fila {idx}. Continuando...")
                        ficha = FichaNegocioLens(id_registro=fila[COLUMNA_ID], estado_ia="ERROR_TIMEOUT", texto_sintesis="[ERROR] Tiempo agotado")
                    except Exception as error:
                        if callback_log:
                            callback_log(f"[ERROR] Fila {idx}: {error}")
                        ficha = FichaNegocioLens(id_registro=fila[COLUMNA_ID], estado_ia="ERROR", texto_sintesis=f"[ERROR] {error}")

                    if ficha.estado_ia == "CANCELADO" or (verificador_cancelacion and verificador_cancelacion()):
                        if callback_log:
                            callback_log("[INFO] Procesamiento de archivo cancelado por el usuario.")
                        break

                    fichas_duplicadas = desglosar_ficha_por_telefono(ficha)
                    ahora_iso = datetime.now(timezone.utc).isoformat()
                    est_val = EstadoIA.EXITOSO.value if ficha.estado_ia == "EXITOSO" else (
                        EstadoIA.FALLIDO.value if "ERROR" in ficha.estado_ia or "TIMEOUT" in ficha.estado_ia else EstadoIA.OMITIDO.value
                    )
                    motivo = f"[{est_val}] {ficha.estado_ia}"
                    fila_salida = dict(fila)
                    datos_ficha = {k: v for k, v in ficha.a_diccionario(normalizado=True).items() if k not in ("metadatos_adicionales", "enlaces")}
                    fila_salida.update(datos_ficha)
                    fila_salida[COLUMNA_ID] = fila[COLUMNA_ID]
                    fila_salida["_estado_ia"] = est_val
                    fila_salida["_motivo_estado"] = motivo
                    fila_salida["_fecha_procesamiento"] = ahora_iso
                    trabajo.confirmar([fila_salida])
                    resultados.extend(fichas_duplicadas)

                    if generar_auditoria_md:
                        try:
                            guardar_auditoria_extraccion_md(ruta_salida.with_suffix(".md"), ficha)
                        except Exception:
                            pass

                    nombre_res = ficha.negocio or ficha.propietario or "Fila procesada"
                    trabajo.notificar_progreso(callback_progreso, idx, f"Completado: {nombre_res}")

                    await asyncio.sleep(0.5)

            finally:
                try:
                    await self._gestor.cerrar_navegador()
                except Exception:
                    pass

            estado = "cancelados" if verificador_cancelacion and verificador_cancelacion() else "completados"
            if estado == "completados" and any(f.estado_ia.startswith(("ERROR", "TIMEOUT")) for f in resultados):
                estado = "fallidos"
            return resultados, trabajo.finalizar(estado, guardar_filas_enriquecidas_csv)
