"""Procesador especializado de imagenes 1 a 1 para Gemini Web y DeepSeek Web."""

from __future__ import annotations

import asyncio
import csv
from collections.abc import Callable
from pathlib import Path
from typing import Any

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.comun.gestor_checkpoint_imagenes import GestorCheckpointImagenes
from procesos_ia.aplicacion.ia_web.comun.gestor_lote_imagenes import (
    listar_imagenes_carpeta,
    recolectar_basura_ciclo,
)
from procesos_ia.aplicacion.ia_web.comun.gestor_resiliencia_web import salvaguardar_progreso_csv
from procesos_ia.aplicacion.ia_web.conversacional.constructor_prompt_imagenes import (
    construir_prompt_extraccion_imagen,
)
from procesos_ia.aplicacion.ia_web.comun.guardador_extracciones import guardar_auditoria_imagen_motores_md
from procesos_ia.aplicacion.ia_web.conversacional.procesador_imagenes_chat import (
    desglosar_fila_por_telefonos,
    normalizar_habla_espanol,
)
from procesos_ia.infraestructura.archivos.escritor_csv import guardar_filas_csv
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.extractor_json import extraer_y_reparar_json
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.infraestructura.web.motores.manipulador_dom_deepseek import (
    enviar_prompt_deepseek,
    esperar_editor_deepseek,
    esperar_respuesta_deepseek,
    iniciar_nuevo_chat_deepseek,
)
from procesos_ia.infraestructura.web.motores.manipulador_dom_gemini import (
    enviar_prompt_gemini,
    esperar_editor_gemini,
    esperar_respuesta_gemini,
    iniciar_nuevo_chat_gemini,
)


class ProcesadorImagenesMotores:
    """Ejecuta extraccion visual 1 a 1 de negocios sobre Gemini o DeepSeek Web."""

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

    async def _obtener_pestana(self, motor: str) -> Any:
        url = self._config.url_gemini if motor == "gemini" else self._config.url_deepseek
        patrones = ("Gemini", "Google") if motor == "gemini" else ("DeepSeek",)
        return await self._gestor.navegar_o_reutilizar(url, patrones)

    async def _rotar_chat(self, pestana: Any, motor: str) -> None:
        if motor == "gemini":
            await iniciar_nuevo_chat_gemini(pestana)
        else:
            await iniciar_nuevo_chat_deepseek(pestana)
        await asyncio.sleep(1.2)

    async def ejecutar(
        self,
        motor: str,
        carpeta: Path,
        campos_activos: list[str] | dict[str, bool],
        instrucciones_adicionales: str = "",
        rotacion_chat: int = 2,
        callback_progreso: Callable[[int, int, str], None] | None = None,
        callback_log: Callable[[str], None] | None = None,
        carpeta_salida: Path | None = None,
        verificador_cancelacion: Callable[[], bool] | None = None,
        archivos_especificos: list[Path] | None = None,
        modo_escritura: str = "sobrescribir",
        csv_existente: Path | None = None,
        generar_auditoria_md: bool = True,
    ) -> tuple[list[dict[str, Any]], Path]:
        """Procesa imagenes 1 a 1 enviando prompt estructurado y rotando sesion."""
        motor = motor.lower().strip()
        archivos = archivos_especificos if archivos_especificos is not None else listar_imagenes_carpeta(carpeta)
        total_archivos = len(archivos)

        todos_resultados: list[dict[str, Any]] = []
        if modo_escritura == "reanudar" and csv_existente and csv_existente.is_file():
            try:
                with open(csv_existente, mode="r", encoding="utf-8-sig", errors="ignore") as f:
                    todos_resultados = [dict(r) for r in csv.DictReader(f)]
                if callback_log:
                    callback_log(f"[INFO] Reanudando: {len(todos_resultados)} filas previas cargadas.")
            except Exception as err_prev:
                if callback_log:
                    callback_log(f"[ALERTA] Error al leer CSV previo: {err_prev}")

        if total_archivos == 0:
            if todos_resultados and csv_existente:
                return todos_resultados, csv_existente
            raise ValueError(f"No se encontraron imágenes compatibles en {carpeta}")

        prompt_base, cols_esp = construir_prompt_extraccion_imagen(
            campos_activos, instrucciones_adicionales
        )
        nombre_csv = f"{motor}_imagenes_{carpeta.name}.csv"
        salida = None
        if modo_escritura == "reanudar" and csv_existente and csv_existente.exists():
            salida = self._enrutador.gestor_procesos(carpeta_salida).retomar(motor, csv_existente)
        if salida is None:
            salida = self._enrutador.reservar_salida(motor, nombre_csv, raiz_destino=carpeta_salida)
        ruta_md = salida.ruta.with_suffix(".md") if generar_auditoria_md else None

        if callback_log:
            txt_modo = f"Reanudando {total_archivos} pendientes" if modo_escritura == "reanudar" else f"{total_archivos} imágenes"
            callback_log(f"[INFO] {motor.upper()} Imágenes 1 a 1: {txt_modo} en '{carpeta.name}' (rotación cada {rotacion_chat} turnos)")

        pestana = await self._obtener_pestana(motor)
        if callback_log:
            callback_log(f"[INFO] Esperando inicialización del editor de {motor.upper()}...")
        editor_listo = (await esperar_editor_gemini(pestana, timeout=25.0)) if motor == "gemini" else (await esperar_editor_deepseek(pestana, timeout=25.0))
        if not editor_listo:
            if callback_log:
                callback_log(f"[ERROR] El editor de {motor.upper()} no respondió tras 25s. Verifique la sesión o conexión.")
            raise RuntimeError(f"Editor de {motor.upper()} no disponible en el DOM")

        hubo_error = False
        imgs_en_chat = 0

        with salida:
            try:
                for idx, ruta_img in enumerate(archivos, start=1):
                    if verificador_cancelacion and verificador_cancelacion():
                        if callback_log:
                            callback_log("[INFO] Proceso cancelado por el usuario.")
                        break

                    if rotacion_chat > 0 and imgs_en_chat >= rotacion_chat:
                        if callback_log:
                            callback_log(f"[INFO] Límite de {rotacion_chat} imágenes alcanzado. Renovando chat en {motor.upper()}...")
                        await self._rotar_chat(pestana, motor)
                        imgs_en_chat = 0
                        # Espera activa del editor tras renovar chat
                        if motor == "gemini":
                            await esperar_editor_gemini(pestana, timeout=15.0)
                        else:
                            await esperar_editor_deepseek(pestana, timeout=15.0)

                    id_registro = f"{ruta_img.stem}_{idx}"
                    if callback_log:
                        callback_log(f"[INFO] ({idx}/{total_archivos}) Enviando imagen a {motor.upper()}: {ruta_img.name}...")

                    t_ini = asyncio.get_event_loop().time()
                    enviado = False
                    for intento in range(1, 3):
                        enviado = (await enviar_prompt_gemini(pestana, prompt_base, ruta_img)) if motor == "gemini" else (await enviar_prompt_deepseek(pestana, prompt_base, ruta_img))
                        if enviado:
                            break
                        if intento < 2:
                            if callback_log:
                                callback_log(f"[ALERTA] Intento {intento}/2 falló al inyectar imagen '{ruta_img.name}'. Reintentando en 2.5s...")
                            await asyncio.sleep(2.5)

                    if not enviado:
                        hubo_error = True
                        fila_err = {"id_registro": id_registro, "archivo_imagen": ruta_img.name, "estado_ia": "ERROR_ENVIO"}
                        todos_resultados.append(fila_err)
                        salvaguardar_progreso_csv(todos_resultados, salida.ruta)
                        if callback_log:
                            callback_log(f"[ERROR] No se pudo enviar imagen '{ruta_img.name}'. Limpiando chat...")
                        try:
                            await self._rotar_chat(pestana, motor)
                            imgs_en_chat = 0
                            if motor == "gemini":
                                await esperar_editor_gemini(pestana, timeout=15.0)
                            else:
                                await esperar_editor_deepseek(pestana, timeout=15.0)
                        except Exception:
                            pass
                        continue

                    resp_txt = (await esperar_respuesta_gemini(pestana, self._config.tiempo_espera_respuesta_segundos, verificador_cancelacion=verificador_cancelacion)) if motor == "gemini" else (await esperar_respuesta_deepseek(pestana, self._config.tiempo_espera_respuesta_segundos, verificador_cancelacion=verificador_cancelacion))
                    t_dur = asyncio.get_event_loop().time() - t_ini
                    if verificador_cancelacion and verificador_cancelacion(): break

                    parsed = extraer_y_reparar_json(resp_txt)
                    fila_base = {
                        "id_registro": id_registro,
                        "archivo_imagen": ruta_img.name,
                        "estado_ia": "EXITOSO" if isinstance(parsed, dict) else "ERROR_PARSE",
                    }
                    if isinstance(parsed, dict):
                        if "nombre_negocio" in parsed and "negocio" not in parsed:
                            parsed["negocio"] = parsed["nombre_negocio"]
                        elif "negocio" in parsed and "nombre_negocio" not in parsed:
                            parsed["nombre_negocio"] = parsed["negocio"]

                        for col in cols_esp:
                            if col not in ("id_registro", "archivo_imagen", "estado_ia"):
                                val_col = parsed.get(col, "ND")
                                if col == "habla_espanol":
                                    val_col = normalizar_habla_espanol(val_col)
                                fila_base[col] = val_col
                    else:
                        fila_base["respuesta_cruda"] = (resp_txt or "")[:300]

                    filas_exp = desglosar_fila_por_telefonos(fila_base)
                    nom_actual = ruta_img.name.lower()
                    todos_resultados = [
                        f for f in todos_resultados
                        if str(f.get("archivo_imagen") or f.get("fuente_imagen") or "").strip().lower() != nom_actual
                        or str(f.get("estado_ia", "")).upper() == "EXITOSO"
                    ]
                    todos_resultados.extend(filas_exp)
                    salvaguardar_progreso_csv(todos_resultados, salida.ruta)
                    if hasattr(self._enrutador, "manifiesto_imagenes"):
                        self._enrutador.manifiesto_imagenes.registrar(carpeta.name, ruta_img.name)

                    imgs_en_chat += 1
                    resumen_neg = str(fila_base.get("negocio") or fila_base.get("nombre_negocio") or "Sin datos")
                    if callback_log:
                        callback_log(f"[OK] ({idx}/{total_archivos}) en {t_dur:.1f}s: {resumen_neg}")
                    if callback_progreso:
                        callback_progreso(idx, total_archivos, f"Imagen {idx}/{total_archivos}: {resumen_neg}")

                    recolectar_basura_ciclo(idx, intervalo=10)
                    if ruta_md:
                        guardar_auditoria_imagen_motores_md(ruta_md, idx, total_archivos, ruta_img.name, fila_base, t_dur, motor)
                    await asyncio.sleep(0.5)

            except Exception as err:
                if not (verificador_cancelacion and verificador_cancelacion()): raise
                if callback_log: callback_log(f"[INFO] Procesamiento cancelado por el usuario: {err}")
            finally:
                if todos_resultados:
                    guardar_filas_csv(todos_resultados, salida.ruta)
                    self._gestor_cp.actualizar_checkpoint(carpeta, motor, todos_resultados, salida.ruta)
                estado = "cancelados" if verificador_cancelacion and verificador_cancelacion() else "completados"
                if estado == "completados" and hubo_error:
                    estado = "fallidos"
                ruta_final = salida.finalizar(estado)
                if todos_resultados:
                    self._gestor_cp.actualizar_checkpoint(carpeta, motor, todos_resultados, ruta_final)
            return todos_resultados, ruta_final

