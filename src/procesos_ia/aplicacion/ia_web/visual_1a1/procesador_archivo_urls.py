"""Modulo de aplicacion para procesamiento por lotes de archivos tabulares (CSV y Excel) con URLs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.comun.guardador_extracciones import (
    guardar_auditoria_extraccion_md,
    guardar_filas_enriquecidas_csv,
)
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
    ) -> tuple[list[FichaNegocioLens], Path]:
        """Procesa registros del archivo tabular enriqueciendolos con datos de Google Lens."""
        t_inicio = asyncio.get_event_loop().time()
        filas = leer_filas_archivo_tabular(ruta_archivo, nombre_hoja=nombre_hoja)
        total = len(filas)
        resultados: list[FichaNegocioLens] = []
        filas_enriquecidas: list[dict[str, Any]] = []

        salida = self._enrutador.reservar_salida(
            "imagenes", f"enriquecido_lens_{ruta_archivo.stem}.csv", raiz_destino=carpeta_salida,
        )
        ruta_salida = salida.ruta

        with salida:
            if callback_log:
                hoja_txt = f" (Hoja: {nombre_hoja})" if nombre_hoja else ""
                callback_log(f"[INFO] Procesando archivo{hoja_txt} con {total} registros en columna '{columna_imagen}': {ruta_archivo.name}")

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
                                    id_registro=f"fila_{idx}",
                                    cerrar_pestana=True,
                                    callback_log=callback_log,
                                ),
                                timeout=tiempo_max,
                            )
                            if valor_img
                            else FichaNegocioLens(id_registro=f"fila_{idx}", texto_sintesis="[INFO] Sin imagen")
                        )
                    except asyncio.TimeoutError:
                        if callback_log:
                            callback_log(f"[ALERTA] Tiempo agotado en fila {idx}. Continuando...")
                        ficha = FichaNegocioLens(id_registro=f"fila_{idx}", estado_ia="ERROR_TIMEOUT", texto_sintesis="[ERROR] Tiempo agotado")
                    except Exception as error:
                        if callback_log:
                            callback_log(f"[ERROR] Fila {idx}: {error}")
                        ficha = FichaNegocioLens(id_registro=f"fila_{idx}", estado_ia="ERROR", texto_sintesis=f"[ERROR] {error}")

                    if ficha.estado_ia == "CANCELADO" or (verificador_cancelacion and verificador_cancelacion()):
                        if callback_log:
                            callback_log("[INFO] Procesamiento de archivo cancelado por el usuario.")
                        break

                    fichas_duplicadas = desglosar_ficha_por_telefono(ficha)
                    resultados.extend(fichas_duplicadas)
                    for f_dup in fichas_duplicadas:
                        fila_salida = dict(fila)
                        fila_salida.update(f_dup.a_diccionario(normalizado=True))
                        filas_enriquecidas.append(fila_salida)

                    if generar_auditoria_md:
                        try:
                            guardar_auditoria_extraccion_md(ruta_salida.with_suffix(".md"), ficha)
                        except Exception:
                            pass

                    nombre_res = ficha.negocio or ficha.propietario or "Fila procesada"
                    if callback_progreso:
                        callback_progreso(idx, total, f"Completado: {nombre_res}")

                    await asyncio.sleep(0.5)

                if filas_enriquecidas:
                    if callback_log:
                        callback_log(f"[INFO] Guardando en el archivo enriquecido: {ruta_salida.name}...")
                    guardar_filas_enriquecidas_csv(filas_enriquecidas, ruta_salida)
                    t_total = asyncio.get_event_loop().time() - t_inicio
                    if callback_log:
                        callback_log(f"[OK] Guardado en CSV: {ruta_salida.resolve()} (Tiempo total: {t_total:.1f}s)")
            finally:
                try:
                    await self._gestor.cerrar_navegador()
                except Exception:
                    pass

            estado = "cancelados" if verificador_cancelacion and verificador_cancelacion() else "completados"
            if estado == "completados" and any(f.estado_ia.startswith(("ERROR", "TIMEOUT")) for f in resultados):
                estado = "fallidos"
            return resultados, salida.finalizar(estado)
