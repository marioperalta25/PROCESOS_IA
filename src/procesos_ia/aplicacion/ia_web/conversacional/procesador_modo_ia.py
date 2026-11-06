"""Modulo de aplicacion para evaluacion por lotes en Modo IA con conversacion estructurada."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
import re
from typing import Any

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.comun.gestor_resiliencia_web import (
    esperar_restablecimiento_conexion,
    filtrar_lineas_datos_ia,
    salvaguardar_progreso_csv,
    verificar_conexion_internet,
)
from procesos_ia.aplicacion.ia_web.comun.guardador_extracciones import (
    guardar_auditoria_modo_ia_md,
    guardar_filas_enriquecidas_csv,
)
from procesos_ia.aplicacion.ia_web.conversacional.formateador_lotes_chat import (
    compactar_instrucciones_prompt,
    construir_mensaje_lote_datos,
    construir_prompt_inicial_conversacion,
)
from procesos_ia.dominio.normalizador import sanear_identificador_columna
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.infraestructura.web.conversacional.manipulador_dom_modo_ia import (
    activar_modo_ia,
    enviar_prompt_modo_ia,
    esperar_respuesta_modo_ia,
    extraer_datos_estructurados_modo_ia,
    extraer_html_ultimo_turno,
    marcar_turnos_previos_modo_ia,
)


def mapear_respuestas_lote(
    texto_resp: str,
    datos: Any,
    lote_actual: list[dict[str, Any]],
    indice_base: int = 1,
) -> list[dict[str, Any]]:
    """Empareja inteligentemente las respuestas de la IA (del 1 al N del lote) con las filas originales."""
    items: list[Any] = []
    if isinstance(datos, dict):
        res = datos.get("resultados") or datos.get("resultado", [])
        items = res if isinstance(res, list) else [res]
    elif isinstance(datos, list):
        items = datos

    mapa: dict[int, dict[str, Any]] = {}
    tamano = len(lote_actual)

    def _resolver(n: int) -> int | None:
        return (n - 1) if (1 <= n <= tamano) else ((n - indice_base) if (indice_base <= n < indice_base + tamano) else None)

    for idx_item, it in enumerate(items):
        if isinstance(it, dict):
            id_val = it.get("id") or it.get("ID") or it.get("fila")
            try:
                id_num = int(id_val) if id_val is not None else (idx_item + 1)
            except (ValueError, TypeError):
                id_num = idx_item + 1
            pos = _resolver(id_num) or (idx_item if idx_item < tamano else None)
            if pos is not None:
                mapa[pos] = {sanear_identificador_columna(k, "col"): v for k, v in it.items() if k.lower() not in ("id", "fila")}
        elif isinstance(it, str) and idx_item < tamano:
            mapa[idx_item] = {"evaluacion_ia": it.strip()}

    if not mapa and texto_resp:
        for linea in texto_resp.splitlines():
            lin = linea.strip()
            if not lin:
                continue
            m = re.match(r"^(?:\[?FILA\s*(\d+)\]?|(\d+)[\.\)\:\-])\s*[:\.\-]?\s*(.*)", lin, re.I)
            if m:
                id_num = int(m.group(1) or m.group(2))
                val = (m.group(3) or "").strip().lstrip(":-. ")
                pos = _resolver(id_num)
                if pos is not None:
                    mapa[pos] = {"evaluacion_ia": val}

    if not mapa and texto_resp:
        for sub_i, lin in enumerate(filtrar_lineas_datos_ia(texto_resp, max_filas=tamano)):
            mapa[sub_i] = {"evaluacion_ia": lin}

    return [dict(f, **mapa.get(idx, {})) for idx, f in enumerate(lote_actual)]


class ProcesadorModoIA:
    """Ejecuta solicitudes en Modo IA con conversacion continua, resiliencia y salvaguarda."""

    def __init__(self, gestor_sesion: GestorSesionNodriver, enrutador: EnrutadorSalidas, configuracion: ConfiguracionWeb) -> None:
        self._gestor = gestor_sesion
        self._enrutador = enrutador
        self._config = configuracion

    async def ejecutar(
        self,
        filas: list[dict[str, Any]],
        instrucciones: str,
        columnas: list[str] | None = None,
        tamano_lote: int = 5,
        lotes_por_conversacion: int = 5,
        callback_progreso: Callable[[int, int, str], None] | None = None,
        callback_log: Callable[[str], None] | None = None,
        nombre_salida: str = "evaluacion",
        carpeta_salida: Path | None = None,
        verificador_cancelacion: Callable[[], bool] | None = None,
        generar_auditoria_md: bool = True,
    ) -> tuple[list[dict[str, Any]], Path | None]:
        """Procesa registros en conversacion continua renovando contexto segun lotes_por_conversacion."""
        total_filas = len(filas)
        total_lotes = (total_filas + tamano_lote - 1) // tamano_lote if total_filas > 0 else 1
        todos_resultados, hubo_error = [], False
        if callback_log:
            callback_log(f"[INFO] Modo IA: {total_filas} filas en {total_lotes} lotes ({tamano_lote} f/lote, {lotes_por_conversacion} l/chat)")
        instrucciones_compactas = compactar_instrucciones_prompt(instrucciones)
        salida = self._enrutador.reservar_salida("modo_ia", f"modo_ia_{nombre_salida}.csv", raiz_destino=carpeta_salida)
        ruta_md = salida.ruta.with_suffix(".md") if generar_auditoria_md else None
        if ruta_md:
            guardar_auditoria_modo_ia_md(ruta_md, 0, total_lotes, 0, 0, "", "", prompt_inicial=instrucciones_compactas)

        with salida:
            try:
                pestana = None
                lotes_en_conversacion = i = reintentos_limite = reintentos_lote = 0
                n_lote = 1

                while i < total_filas:
                    if verificador_cancelacion and verificador_cancelacion():
                        if callback_log:
                            callback_log("[INFO] Proceso de Modo IA cancelado por el usuario.")
                        break

                    if not verificar_conexion_internet():
                        await esperar_restablecimiento_conexion(callback_log)
                        pestana = None
                        continue

                    lote_actual = filas[i : i + tamano_lote]
                    indice_base = i + 1

                    if pestana is None or lotes_en_conversacion >= lotes_por_conversacion:
                        if pestana is not None:
                            if callback_log:
                                callback_log(f"[INFO] Límite de {lotes_por_conversacion} lote(s) por chat alcanzado. Renovando conversación...")
                            await pestana.get("https://www.google.com")
                            await asyncio.sleep(0.3)
                        else:
                            pestana = await self._gestor.abrir_nueva_pestana("https://www.google.com")
                            await asyncio.sleep(0.3)

                        await activar_modo_ia(pestana)
                        lotes_en_conversacion = 0
                        if callback_log:
                            callback_log(f"[INFO] Enviando prompt inicial del sistema ({len(instrucciones_compactas)} caracteres)...")

                        prompt_inicial = construir_prompt_inicial_conversacion(instrucciones_compactas)
                        turnos_inicio = await marcar_turnos_previos_modo_ia(pestana)
                        enviado_inicial = await enviar_prompt_modo_ia(pestana, prompt_inicial)
                        if not enviado_inicial:
                            hubo_error = True
                            if callback_log:
                                callback_log("[ERROR] No se pudo enviar el prompt inicial a Modo IA. Reintentando...")
                            pestana = None
                            await asyncio.sleep(0.5)
                            continue

                        resp_inicio = await esperar_respuesta_modo_ia(
                            pestana, self._config.tiempo_espera_respuesta_segundos, turnos_previos=turnos_inicio
                        )
                        if not resp_inicio.strip():
                            if callback_log:
                                callback_log("[ALERTA] Modo IA no confirmó el prompt del sistema. Reintentando inicio...")
                            pestana = None
                            continue
                        await asyncio.sleep(0.3)

                    fila_desde = i + 1
                    fila_hasta = min(i + len(lote_actual), total_filas)
                    if callback_log:
                        callback_log(f"[INFO] Enviando Lote {n_lote}/{total_lotes} (filas {fila_desde}-{fila_hasta} de {total_filas}) con '|'...")

                    mensaje_lote = construir_mensaje_lote_datos(lote_filas=lote_actual, columnas_seleccionadas=columnas, indice_inicio=1)
                    turnos_antes = await marcar_turnos_previos_modo_ia(pestana)
                    enviado = await enviar_prompt_modo_ia(pestana, mensaje_lote)
                    if not enviado:
                        hubo_error = True
                        if callback_log:
                            callback_log(f"[ERROR] Falló envío en Lote {n_lote}")
                        continue

                    t_inicio_lote = asyncio.get_event_loop().time()
                    texto_resp = await esperar_respuesta_modo_ia(
                        pestana, self._config.tiempo_espera_respuesta_segundos,
                        turnos_previos=turnos_antes, filas_esperadas=len(lote_actual),
                    )
                    t_duracion = asyncio.get_event_loop().time() - t_inicio_lote

                    es_limite = bool(re.search(
                        r"alcanzaste el l[ií]mite de solicitudes|l[ií]mite de respuestas de ia|vuelve a intentarlo m[aá]s tarde|reached the limit of ai",
                        texto_resp, re.IGNORECASE,
                    ))

                    if not texto_resp.strip() or re.search(r"estoy listo para procesar|env[ií]a el primer lote", texto_resp, re.I):
                        if callback_log:
                            callback_log(f"[ALERTA] Respuesta no válida en Lote {n_lote}. Reintentando espera...")
                        await asyncio.sleep(1.0)
                        continue

                    if es_limite:
                        reintentos_limite += 1
                        if callback_log:
                            callback_log(f"[ALERTA] Límite de IA en Google. Reiniciando perfil para Lote {n_lote} (intento {reintentos_limite}/3)...")
                        pestana, lotes_en_conversacion = None, 0
                        await self._gestor.reiniciar_con_perfil_limpio()
                        await asyncio.sleep(2.0)
                        if reintentos_limite > 3:
                            if callback_log:
                                callback_log("[ERROR] Límite persistente tras 3 reinicios. Deteniendo proceso.")
                            break
                        continue

                    reintentos_limite = 0
                    if callback_log:
                        callback_log(f"[OK] Lote {n_lote}/{total_lotes} respondido en {t_duracion:.1f}s.")

                    html_crudo = ""
                    if ruta_md:
                        html_crudo = await extraer_html_ultimo_turno(pestana)
                        guardar_auditoria_modo_ia_md(
                            ruta_md, n_lote, total_lotes, fila_desde, fila_hasta,
                            mensaje_lote, texto_resp, t_duracion, html_crudo=html_crudo,
                        )

                    datos = extraer_datos_estructurados_modo_ia(texto_resp)
                    filas_lote = mapear_respuestas_lote(texto_resp=texto_resp, datos=datos, lote_actual=lote_actual, indice_base=indice_base)
                    evaluadas = sum(1 for f in filas_lote if f.get("evaluacion_ia"))

                    if evaluadas == 0 and reintentos_lote < 2:
                        reintentos_lote += 1
                        if callback_log:
                            callback_log(f"[ALERTA] Lote {n_lote} devolvió 0 filas evaluadas. Reintentando lote ({reintentos_lote}/2)...")
                        pestana, lotes_en_conversacion = None, 0
                        await asyncio.sleep(1.0)
                        continue
                    reintentos_lote = 0

                    if callback_log and evaluadas < len(lote_actual):
                        callback_log(f"[ALERTA] Lote {n_lote} evaluó {evaluadas}/{len(lote_actual)} filas (IA omitió {len(lote_actual)-evaluadas}).")

                    todos_resultados.extend(filas_lote)
                    salvaguardar_progreso_csv(todos_resultados, salida.ruta)
                    lotes_en_conversacion += 1

                    if callback_progreso:
                        callback_progreso(min(i + tamano_lote, total_filas), total_filas, f"Lote {n_lote}/{total_lotes} procesado")
                    await asyncio.sleep(0.3)
                    i += tamano_lote
                    n_lote += 1

                ruta_salida = salida.ruta
                if todos_resultados:
                    guardar_filas_enriquecidas_csv(todos_resultados, ruta_salida)
                    if callback_log:
                        callback_log(f"[OK] Guardado en CSV: {ruta_salida.resolve()}")
                if ruta_md and callback_log:
                    callback_log(f"[OK] Bitácora de inspección guardada en: {ruta_md.resolve()}")

            finally:
                await self._gestor.cerrar_navegador()

            estado = "cancelados" if verificador_cancelacion and verificador_cancelacion() else "completados"
            if estado == "completados" and hubo_error:
                estado = "fallidos"
            return todos_resultados, salida.finalizar(estado)
