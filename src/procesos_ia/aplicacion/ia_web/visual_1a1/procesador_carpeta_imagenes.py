"""Modulo de aplicacion para procesamiento por lotes de carpetas locales de imagenes en Lens."""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from collections.abc import Callable
from pathlib import Path
from typing import Any

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.comun.guardador_extracciones import guardar_auditoria_extraccion_md
from procesos_ia.aplicacion.ia_web.comun.gestor_lote_imagenes import (
    escribir_fila_incremental_csv,
    generar_ruta_csv_salida,
    listar_imagenes_carpeta,
    recolectar_basura_ciclo,
)
from procesos_ia.dominio.ia_web.desglosador_telefonos import desglosar_ficha_por_telefono
from procesos_ia.dominio.ia_web.ficha_negocio import FichaNegocioLens
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver

COLUMNAS_CARPETA = [
    "id_registro", "estado_ia", "propietario", "negocio", "categoria", "telefono",
    "ubicacion", "licencia", "correo_electronico", "sitio_web", "idiomas", "enlaces_str",
    "texto_sintesis", "fuente_imagen",
]


class ProcesadorCarpetaImagenes:
    """Procesa una coleccion de imagenes de forma incremental O(1) con tolerancia a fallos."""

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
        carpeta: Path,
        callback_progreso: Callable[[int, int, str], None] | None = None,
        callback_log: Callable[[str], None] | None = None,
        archivos_especificos: list[Path] | None = None,
        modo_escritura: str = "sobrescribir",
        csv_existente: Path | None = None,
        carpeta_salida: Path | None = None,
        verificador_cancelacion: Callable[[], bool] | None = None,
        generar_auditoria_md: bool = True,
    ) -> tuple[list[FichaNegocioLens], Path]:
        """Ejecuta el procesamiento incremental de las imagenes de una carpeta."""
        t_inicio = asyncio.get_event_loop().time()
        archivos = archivos_especificos if archivos_especificos is not None else listar_imagenes_carpeta(carpeta)
        total = len(archivos)
        resultados: list[FichaNegocioLens] = []
        salida = None
        if modo_escritura == "reanudar" and csv_existente and csv_existente.exists():
            ruta_csv = csv_existente
            salida = self._enrutador.gestor_procesos(carpeta_salida).retomar("imagenes", ruta_csv)
            if salida is not None:
                ruta_csv = salida.ruta
            if callback_log:
                callback_log(f"[INFO] Reanudando procesamiento sobre: {ruta_csv.name}")
        else:
            nombre = generar_ruta_csv_salida(Path(), carpeta.name).name
            salida = self._enrutador.reservar_salida("imagenes", nombre, raiz_destino=carpeta_salida)
            ruta_csv = salida.ruta
            if callback_log:
                callback_log(f"[INFO] Iniciando nuevo archivo incremental: {ruta_csv.name}")

        with salida if salida is not None else nullcontext():
            try:
                for idx, img in enumerate(archivos, start=1):
                    if verificador_cancelacion and verificador_cancelacion():
                        if callback_log:
                            callback_log("[INFO] Procesamiento de carpeta cancelado por el usuario.")
                        break

                    id_reg = f"{img.stem}_{idx}"
                    if callback_log:
                        callback_log(f"[INFO] ({idx}/{total}) Procesando: {img.name}")
                    try:
                        tiempo_maximo = max(float(self._config.tiempo_espera_respuesta_segundos) + 8.0, 20.0)
                        ficha = await asyncio.wait_for(
                            self._ejecutor_lens(
                                fuente_imagen=str(img),
                                id_registro=id_reg,
                                cerrar_pestana=True,
                                callback_log=callback_log,
                            ),
                            timeout=tiempo_maximo,
                        )
                    except asyncio.TimeoutError:
                        if callback_log:
                            callback_log(f"[ALERTA] Tiempo agotado en {img.name}. Continuando...")
                        ficha = FichaNegocioLens(id_registro=id_reg, fuente_imagen=img.name, estado_ia="ERROR_TIMEOUT", texto_sintesis="[ERROR] Tiempo agotado")
                    except Exception as error:
                        if callback_log:
                            callback_log(f"[ERROR] Error al procesar imagen {img.name}: {error}")
                        ficha = FichaNegocioLens(id_registro=id_reg, fuente_imagen=img.name, estado_ia="ERROR", texto_sintesis=f"[ERROR] {error}")

                    if ficha.estado_ia == "CANCELADO" or (verificador_cancelacion and verificador_cancelacion()):
                        if callback_log:
                            callback_log("[INFO] Procesamiento de carpeta cancelado por el usuario.")
                        break

                    fichas_duplicadas = desglosar_ficha_por_telefono(ficha)
                    for f_dup in fichas_duplicadas:
                        try:
                            escribir_fila_incremental_csv(f_dup.a_diccionario(normalizado=True), ruta_csv, COLUMNAS_CARPETA)
                        except Exception as err_esc:
                            if callback_log:
                                callback_log(f"[ALERTA] Error al escribir fila: {err_esc}")
                            raise
                    if generar_auditoria_md:
                        try:
                            guardar_auditoria_extraccion_md(ruta_csv.with_suffix(".md"), ficha)
                        except Exception:
                            pass
                    if hasattr(self._enrutador, "manifiesto_imagenes"):
                        self._enrutador.manifiesto_imagenes.registrar(carpeta.name, img.name)
                    resultados.extend(fichas_duplicadas)

                    nombre_res = ficha.negocio or ficha.propietario or "Ficha"
                    if callback_progreso:
                        callback_progreso(idx, total, f"Completado ({idx}/{total}): {nombre_res}")

                    recolectar_basura_ciclo(idx, intervalo=10)
                    await asyncio.sleep(0.5)

                t_total = asyncio.get_event_loop().time() - t_inicio
                con_ia = sum(1 for f in resultados if f.estado_ia == "EXITOSO")
                if callback_log:
                    callback_log(f"[OK] Lote finalizado ({con_ia}/{len(resultados)} con IA). Tiempo: {t_total:.1f}s.")
                    callback_log(f"[OK] Guardado en CSV: {ruta_csv.resolve()}")
            finally:
                try:
                    await self._gestor.cerrar_navegador()
                except Exception:
                    pass

            if salida is not None:
                estado = "cancelados" if verificador_cancelacion and verificador_cancelacion() else "completados"
                if estado == "completados" and any(f.estado_ia.startswith(("ERROR", "TIMEOUT")) for f in resultados):
                    estado = "fallidos"
                ruta_csv = salida.finalizar(estado)
            return resultados, ruta_csv
