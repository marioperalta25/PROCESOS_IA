"""Modulo de aplicacion para procesamiento 1 a 1 de carpetas de imagenes en Modo IA."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
from pathlib import Path
import re
from typing import Any

from procesos_ia.aplicacion.comun.gestor_checkpoint_imagenes import GestorCheckpointImagenes
from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.comun.gestor_lote_imagenes import (
    listar_imagenes_carpeta,
    recolectar_basura_ciclo,
)
from procesos_ia.aplicacion.ia_web.comun.gestor_resiliencia_web import (
    esperar_restablecimiento_conexion,
    recuperar_si_captcha_google,
    salvaguardar_progreso_csv,
    verificar_conexion_internet,
)
from procesos_ia.aplicacion.ia_web.comun.guardador_extracciones import (
    guardar_auditoria_modo_ia_md,
    guardar_filas_enriquecidas_csv,
)
from procesos_ia.aplicacion.ia_web.conversacional.constructor_prompt_imagenes import (
    construir_prompt_extraccion_imagen,
)
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.extractor_json import extraer_y_reparar_json
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.infraestructura.web.conversacional.inyector_imagen_modo_ia import (
    inyectar_imagen_y_prompt_modo_ia,
)
from procesos_ia.infraestructura.web.conversacional.manipulador_dom_modo_ia import (
    activar_modo_ia,
    esperar_respuesta_modo_ia,
    extraer_html_ultimo_turno,
    marcar_turnos_previos_modo_ia,
)


def normalizar_habla_espanol(valor: Any) -> str:
    """Normaliza el campo habla_espanol a 'habla espanol' o 'No'."""
    val_str = str(valor).strip().lower()
    if val_str in ("habla espanol", "habla español", "si", "sí", "yes", "true", "1"):
        return "habla espanol"
    return "No"


def desglosar_fila_por_telefonos(fila: dict[str, Any]) -> list[dict[str, Any]]:
    """Duplica la fila manteniendo los campos originales si la IA detecto multiples telefonos."""
    tel_raw = str(fila.get("telefonos", "")).strip()
    if not tel_raw or tel_raw.upper() in ("ND", "NULL", "NONE"):
        return [fila]
    partes = [p.strip() for p in re.split(r"\s*/\s*|\s*;\s*|\n+", tel_raw) if p.strip()]
    if len(partes) <= 1:
        return [fila]
    filas_duplicadas = []
    base_id = str(fila.get("id_registro", "img"))
    for idx_tel, tel in enumerate(partes, 1):
        f = dict(fila)
        f["telefonos"] = tel
        f["id_registro"] = f"{base_id}_t{idx_tel}"
        filas_duplicadas.append(f)
    return filas_duplicadas


class ProcesadorImagenesChat:
    """Ejecuta extraccion visual 1 a 1 de carpetas de imagenes en Modo IA con rotacion cada 3 turnos."""

    def __init__(
        self,
        gestor_sesion: GestorSesionNodriver,
        enrutador: EnrutadorSalidas,
        configuracion: ConfiguracionWeb,
    ) -> None:
        self._gestor = gestor_sesion
        self._enrutador = enrutador
        self._config = configuracion
        self._gestor_cp = GestorCheckpointImagenes(enrutador)

    async def ejecutar(
        self,
        carpeta: Path,
        campos_activos: list[str] | dict[str, bool],
        instrucciones_adicionales: str = "",
        rotacion_chat: int = 3,
        callback_progreso: Callable[[int, int, str], None] | None = None,
        callback_log: Callable[[str], None] | None = None,
        carpeta_salida: Path | None = None,
        verificador_cancelacion: Callable[[], bool] | None = None,
        generar_auditoria_md: bool = True,
        archivos_especificos: list[Path] | None = None,
        modo_escritura: str = "sobrescribir",
        csv_existente: Path | None = None,
    ) -> tuple[list[dict[str, Any]], Path | None]:
        """Procesa cada imagen de la carpeta enviando prompt y rotando chat cada rotacion_chat imagenes."""
        archivos = archivos_especificos if archivos_especificos is not None else listar_imagenes_carpeta(carpeta)
        total_archivos = len(archivos)

        todos_resultados: list[dict[str, Any]] = []
        if modo_escritura == "reanudar" and csv_existente and csv_existente.is_file():
            try:
                import csv
                with open(csv_existente, mode="r", encoding="utf-8-sig", errors="ignore") as f:
                    todos_resultados = [dict(r) for r in csv.DictReader(f)]
                if callback_log:
                    callback_log(f"[INFO] Reanudando: {len(todos_resultados)} filas previas cargadas.")
            except Exception as err_prev:
                if callback_log:
                    callback_log(f"[ALERTA] No se pudo leer CSV previo: {err_prev}")

        if total_archivos == 0:
            if todos_resultados:
                return todos_resultados, csv_existente
            raise ValueError(f"No se encontraron imágenes compatibles (.jpg, .png, .webp) en {carpeta}")

        prompt_base, columnas_esperadas = construir_prompt_extraccion_imagen(
            campos_activos, instrucciones_adicionales
        )

        nombre_csv = f"modo_ia_imagenes_{carpeta.name}.csv"
        salida = None
        if modo_escritura == "reanudar" and csv_existente and csv_existente.exists():
            salida = self._enrutador.gestor_procesos(carpeta_salida).retomar("modo_ia", csv_existente)
        if salida is None:
            salida = self._enrutador.reservar_salida("modo_ia", nombre_csv, raiz_destino=carpeta_salida)

        ruta_md = salida.ruta.with_suffix(".md") if generar_auditoria_md else None
        if ruta_md:
            guardar_auditoria_modo_ia_md(
                ruta_md, 0, total_archivos, 0, 0, "", "", prompt_inicial=prompt_base
            )

        if callback_log:
            txt_modo = f"Reanudando {total_archivos} pendientes" if modo_escritura == "reanudar" else f"{total_archivos} imágenes"
            callback_log(f"[INFO] Modo IA Imágenes: {txt_modo} en '{carpeta.name}' (rotación cada {rotacion_chat} imgs)")

        hubo_error = False

        with salida:
            try:
                pestana = None
                imgs_en_chat = reintentos_captcha = 0
                detener_por_captcha = False

                for idx, ruta_img in enumerate(archivos, start=1):
                    if detener_por_captcha: break
                    while True:
                        if verificador_cancelacion and verificador_cancelacion():
                            if callback_log: callback_log("[INFO] Proceso de imágenes cancelado por el usuario.")
                            detener_por_captcha = True; break

                        if not verificar_conexion_internet():
                            await esperar_restablecimiento_conexion(callback_log); pestana = None

                        id_registro = f"{ruta_img.stem}_{idx}"
                        if pestana is None or imgs_en_chat >= rotacion_chat:
                            if pestana is not None and callback_log:
                                callback_log(f"[INFO] Límite de {rotacion_chat} imágenes por chat alcanzado. Renovando conversación...")
                            pestana = await self._gestor.abrir_nueva_pestana("https://www.google.com")
                            aviso_v = getattr(self._gestor, "ultimo_aviso_ventana", None)
                            if aviso_v and callback_log: callback_log(f"[ALERTA] {aviso_v}")
                            await asyncio.sleep(0.3); await activar_modo_ia(pestana); imgs_en_chat = 0
                            if await recuperar_si_captcha_google(pestana, self._gestor, callback_log):
                                pestana = None; reintentos_captcha += 1
                                if reintentos_captcha > 3:
                                    if callback_log: callback_log("[ERROR] CAPTCHA persistente tras 3 reinicios de perfil. Deteniendo proceso.")
                                    detener_por_captcha = True; break
                                continue

                        if callback_log: callback_log(f"[INFO] ({idx}/{total_archivos}) Enviando imagen: {ruta_img.name}...")
                        turnos_antes = await marcar_turnos_previos_modo_ia(pestana)
                        enviado = False
                        for intento in range(1, 3):
                            enviado = await inyectar_imagen_y_prompt_modo_ia(pestana, prompt_base, ruta_imagen=ruta_img)
                            if enviado: break
                            if intento < 2:
                                if callback_log: callback_log(f"[ALERTA] Intento {intento}/2 falló al inyectar '{ruta_img.name}'. Reintentando en 2.5s...")
                                await asyncio.sleep(2.5)

                        if not enviado:
                            if await recuperar_si_captcha_google(pestana, self._gestor, callback_log):
                                pestana = None; imgs_en_chat = 0; reintentos_captcha += 1
                                if reintentos_captcha > 3:
                                    if callback_log: callback_log("[ERROR] CAPTCHA persistente tras 3 reinicios de perfil. Deteniendo proceso.")
                                    detener_por_captcha = True; break
                                continue
                            hubo_error = True
                            if callback_log: callback_log(f"[ERROR] No se pudo enviar imagen '{ruta_img.name}'. Renovando conversación...")
                            todos_resultados.append({"id_registro": id_registro, "archivo_imagen": ruta_img.name, "estado_ia": "ERROR_ENVIO"})
                            salvaguardar_progreso_csv(todos_resultados, salida.ruta)
                            pestana = None; imgs_en_chat = 0; break

                        t_inicio = asyncio.get_running_loop().time()
                        resp_texto = await esperar_respuesta_modo_ia(
                            pestana, self._config.tiempo_espera_respuesta_segundos,
                            turnos_previos=turnos_antes, filas_esperadas=1, verificador_cancelacion=verificador_cancelacion,
                        )
                        t_dur = asyncio.get_running_loop().time() - t_inicio
                        if verificador_cancelacion and verificador_cancelacion():
                            detener_por_captcha = True; break
                        if not resp_texto.strip() and await recuperar_si_captcha_google(pestana, self._gestor, callback_log):
                            pestana = None; imgs_en_chat = 0; reintentos_captcha += 1
                            if reintentos_captcha > 3:
                                if callback_log: callback_log("[ERROR] CAPTCHA persistente tras 3 reinicios de perfil. Deteniendo proceso.")
                                detener_por_captcha = True; break
                            continue
                        reintentos_captcha = 0; break
                    if detener_por_captcha:
                        break
                    if not enviado:
                        continue

                    html_crudo = ""
                    if ruta_md:
                        html_crudo = await extraer_html_ultimo_turno(pestana)
                        guardar_auditoria_modo_ia_md(
                            ruta_md, idx, total_archivos, idx, idx,
                            f"Imagen: {ruta_img.name}", resp_texto, t_dur, html_crudo=html_crudo,
                        )

                    # Extracción y estructuración de la respuesta JSON
                    datos_parsed = extraer_y_reparar_json(resp_texto)
                    fila_base = {
                        "id_registro": id_registro,
                        "archivo_imagen": ruta_img.name,
                        "estado_ia": "EXITOSO" if isinstance(datos_parsed, dict) else "ERROR_PARSE",
                    }
                    if isinstance(datos_parsed, dict):
                        if "nombre_negocio" in datos_parsed and "negocio" not in datos_parsed:
                            datos_parsed["negocio"] = datos_parsed["nombre_negocio"]
                        elif "negocio" in datos_parsed and "nombre_negocio" not in datos_parsed:
                            datos_parsed["nombre_negocio"] = datos_parsed["negocio"]

                        for col in columnas_esperadas:
                            if col not in ("id_registro", "archivo_imagen", "estado_ia"):
                                val_col = datos_parsed.get(col, "ND")
                                if col == "habla_espanol":
                                    val_col = normalizar_habla_espanol(val_col)
                                fila_base[col] = val_col
                    else:
                        fila_base["respuesta_cruda"] = resp_texto[:300] if resp_texto else "ND"

                    # Desglose de filas si hay múltiples teléfonos detectados
                    filas_expandidas = desglosar_fila_por_telefonos(fila_base)
                    nom_actual = ruta_img.name.lower()
                    todos_resultados = [
                        f for f in todos_resultados
                        if str(f.get("archivo_imagen") or f.get("fuente_imagen") or "").strip().lower() != nom_actual
                        or str(f.get("estado_ia", "")).upper() == "EXITOSO"
                    ]
                    todos_resultados.extend(filas_expandidas)
                    salvaguardar_progreso_csv(todos_resultados, salida.ruta)
                    if hasattr(self._enrutador, "manifiesto_imagenes"):
                        self._enrutador.manifiesto_imagenes.registrar(
                            carpeta.name, ruta_img.name
                        )

                    imgs_en_chat += 1
                    resumen_neg = str(fila_base.get("negocio") or fila_base.get("nombre_negocio") or "Sin datos")
                    if callback_log:
                        callback_log(
                            f"[OK] Imagen {idx}/{total_archivos} respondida en {t_dur:.1f}s: {resumen_neg}"
                        )
                    if callback_progreso:
                        callback_progreso(
                            idx, total_archivos, f"Imagen {idx}/{total_archivos}: {resumen_neg}"
                        )

                    recolectar_basura_ciclo(idx, intervalo=10)
                    await asyncio.sleep(0.4)

            except Exception as err:
                if not (verificador_cancelacion and verificador_cancelacion()): raise
                if callback_log: callback_log(f"[INFO] Tarea interrumpida por cancelacion: {err}")
            finally:
                try:
                    await asyncio.wait_for(self._gestor.cerrar_navegador(), timeout=1.2)
                except Exception:
                    pass
                if todos_resultados:
                    guardar_filas_enriquecidas_csv(todos_resultados, salida.ruta)
                    self._gestor_cp.actualizar_checkpoint(carpeta, "modo_ia", todos_resultados, salida.ruta)
                estado = "cancelados" if (verificador_cancelacion and verificador_cancelacion()) else "completados"
                if estado == "completados" and hubo_error:
                    estado = "fallidos"
                ruta_final = salida.finalizar(estado)
                if todos_resultados:
                    self._gestor_cp.actualizar_checkpoint(carpeta, "modo_ia", todos_resultados, ruta_final)
            return todos_resultados, ruta_final

