"""Modulo de aplicacion para evaluacion por lotes en Modo IA con conversacion estructurada."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
import re
from typing import Any

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.comun.gestor_reanudacion_base import (
    COLUMNA_ESTADO, COLUMNA_FECHA, COLUMNA_ID, COLUMNA_MOTIVO, GestorReanudacionBase,
)
from procesos_ia.aplicacion.ia_web.comun.diagnostico_lotes import (
    detectar_limite_cuota, evaluar_calidad_lote, notificar_alerta_confirmacion_inicio,
    notificar_balance_lote, notificar_cierre_exitoso, notificar_envio_lote,
    notificar_envio_prompt_sistema, notificar_fallo_envio_lote,
    notificar_fallo_prompt_sistema, notificar_inicio_proceso,
    notificar_limite_cuota, notificar_limite_persistente,
    notificar_reintento_lote, notificar_respuesta_lote,
)
from procesos_ia.aplicacion.ia_web.comun.gestor_resiliencia_web import (
    esperar_restablecimiento_conexion, filtrar_lineas_datos_ia,
    salvaguardar_progreso_csv, verificar_conexion_internet,
)
from procesos_ia.aplicacion.ia_web.comun.guardador_extracciones import (
    guardar_auditoria_modo_ia_md, guardar_filas_enriquecidas_csv,
)
from procesos_ia.aplicacion.ia_web.conversacional.formateador_lotes_chat import (
    compactar_instrucciones_prompt, construir_mensaje_lote_datos,
    construir_prompt_inicial_conversacion,
)
from procesos_ia.dominio.reanudacion import EstadoIA
from procesos_ia.dominio.normalizador import sanear_identificador_columna
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.infraestructura.web.conversacional.manipulador_dom_modo_ia import (
    activar_modo_ia, enviar_prompt_modo_ia, esperar_respuesta_modo_ia,
    extraer_datos_estructurados_modo_ia, extraer_html_ultimo_turno,
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

    filas_enriquecidas = []
    fecha_iso = GestorReanudacionBase.fecha_actual_iso()
    for idx, f in enumerate(lote_actual):
        f_res = dict(f)
        eval_dict = mapa.get(idx)
        if eval_dict and eval_dict.get("evaluacion_ia"):
            f_res.update(eval_dict)
            f_res[COLUMNA_ESTADO] = EstadoIA.EXITOSO.value
            f_res[COLUMNA_MOTIVO] = "[OK] Evaluado"
        else:
            f_res[COLUMNA_ESTADO] = EstadoIA.OMITIDO.value
            f_res[COLUMNA_MOTIVO] = "[ALERTA] No devuelto por LLM en este lote"
        f_res[COLUMNA_FECHA] = fecha_iso
        filas_enriquecidas.append(f_res)
    return filas_enriquecidas


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
        salida_existente: Any | None = None,
    ) -> tuple[list[dict[str, Any]], Path | None]:
        """Procesa registros en conversacion continua renovando contexto segun lotes_por_conversacion."""
        total_filas = len(filas)
        total_lotes = (total_filas + tamano_lote - 1) // tamano_lote if total_filas > 0 else 1
        todos_resultados, hubo_error = [], False
        notificar_inicio_proceso(callback_log, "Modo IA de Google", total_filas, total_lotes, tamano_lote, lotes_por_conversacion)
        instrucciones_compactas = compactar_instrucciones_prompt(instrucciones)
        salida = salida_existente or self._enrutador.reservar_salida("modo_ia", f"modo_ia_{nombre_salida}.csv", raiz_destino=carpeta_salida)
        ruta_md = salida.ruta.with_suffix(".md") if generar_auditoria_md else None
        if ruta_md and not ruta_md.exists():
            guardar_auditoria_modo_ia_md(ruta_md, 0, total_lotes, 0, 0, "", "", prompt_inicial=instrucciones_compactas)

        with salida:
            try:
                pestana = None
                lotes_en_conversacion = i = reintentos_limite = reintentos_lote = 0
                n_lote = 1

                while i < total_filas:
                    if verificador_cancelacion and verificador_cancelacion(): break
                    if not verificar_conexion_internet():
                        await esperar_restablecimiento_conexion(callback_log); pestana = None; continue

                    lote_actual = filas[i : i + tamano_lote]; indice_base = i + 1
                    if pestana is None or lotes_en_conversacion >= lotes_por_conversacion:
                        if pestana is not None:
                            if callback_log: callback_log(f"[INFO] Límite de {lotes_por_conversacion} lote(s) alcanzado. Renovando conversación...")
                            await pestana.get("https://www.google.com"); await asyncio.sleep(0.3)
                        else:
                            pestana = await self._gestor.abrir_nueva_pestana("https://www.google.com"); await asyncio.sleep(0.3)
                        await activar_modo_ia(pestana); lotes_en_conversacion = 0
                        if verificador_cancelacion and verificador_cancelacion(): break
                        notificar_envio_prompt_sistema(callback_log, len(instrucciones_compactas))
                        prompt_inicial = construir_prompt_inicial_conversacion(instrucciones_compactas, columnas_seleccionadas=columnas, tamano_lote=tamano_lote)
                        turnos_inicio = await marcar_turnos_previos_modo_ia(pestana)
                        enviado_inicial = await enviar_prompt_modo_ia(pestana, prompt_inicial)
                        if not enviado_inicial:
                            hubo_error = True; notificar_fallo_prompt_sistema(callback_log); pestana = None; await asyncio.sleep(0.5); continue
                        resp_inicio = await esperar_respuesta_modo_ia(
                            pestana, self._config.tiempo_espera_respuesta_segundos, turnos_previos=turnos_inicio,
                            verificador_cancelacion=verificador_cancelacion,
                        )
                        if not resp_inicio.strip():
                            notificar_alerta_confirmacion_inicio(callback_log); pestana = None; continue
                        await asyncio.sleep(0.3)

                    if verificador_cancelacion and verificador_cancelacion(): break
                    fila_desde, fila_hasta = i + 1, min(i + len(lote_actual), total_filas)
                    notificar_envio_lote(callback_log, n_lote, total_lotes, fila_desde, fila_hasta, total_filas, delimitador="|")
                    mensaje_lote = construir_mensaje_lote_datos(lote_filas=lote_actual, columnas_seleccionadas=columnas, indice_inicio=1)
                    turnos_antes = await marcar_turnos_previos_modo_ia(pestana)
                    enviado = await enviar_prompt_modo_ia(pestana, mensaje_lote)
                    if not enviado:
                        hubo_error = True; notificar_fallo_envio_lote(callback_log, n_lote); continue
                    if verificador_cancelacion and verificador_cancelacion(): break

                    t_inicio_lote = asyncio.get_event_loop().time()
                    texto_resp = await esperar_respuesta_modo_ia(
                        pestana, self._config.tiempo_espera_respuesta_segundos,
                        turnos_previos=turnos_antes, filas_esperadas=len(lote_actual),
                        verificador_cancelacion=verificador_cancelacion,
                    )
                    t_duracion = asyncio.get_event_loop().time() - t_inicio_lote
                    if verificador_cancelacion and verificador_cancelacion(): break

                    if not texto_resp.strip() or re.search(r"estoy listo para procesar|env[ií]a el primer lote", texto_resp, re.I):
                        if callback_log: callback_log(f"[ALERTA] Respuesta no válida en Lote {n_lote}. Reintentando espera...")
                        await asyncio.sleep(1.0); continue

                    if detectar_limite_cuota(texto_resp):
                        reintentos_limite += 1; pestana, lotes_en_conversacion = None, 0
                        notificar_limite_cuota(callback_log, "Google Modo IA", n_lote, reintentos_limite, 3)
                        await self._gestor.reiniciar_con_perfil_limpio(); await asyncio.sleep(2.0)
                        if reintentos_limite > 3:
                            notificar_limite_persistente(callback_log, 3); break
                        continue
                    reintentos_limite = 0
                    notificar_respuesta_lote(callback_log, n_lote, total_lotes, t_duracion)
                    if ruta_md:
                        html_crudo = await extraer_html_ultimo_turno(pestana)
                        guardar_auditoria_modo_ia_md(ruta_md, n_lote, total_lotes, fila_desde, fila_hasta, mensaje_lote, texto_resp, t_duracion, html_crudo=html_crudo)
                    datos = extraer_datos_estructurados_modo_ia(texto_resp)
                    filas_lote = mapear_respuestas_lote(texto_resp=texto_resp, datos=datos, lote_actual=lote_actual, indice_base=indice_base)
                    evaluadas, omitidas = evaluar_calidad_lote(filas_lote, len(lote_actual))
                    if evaluadas == 0 and reintentos_lote < 2:
                        reintentos_lote += 1; notificar_reintento_lote(callback_log, n_lote, reintentos_lote, 2)
                        pestana, lotes_en_conversacion = None, 0; await asyncio.sleep(1.0); continue
                    reintentos_lote = 0
                    notificar_balance_lote(callback_log, n_lote, evaluadas, len(lote_actual))
                    todos_resultados.extend(filas_lote)
                    salvaguardar_progreso_csv(todos_resultados, salida.ruta)
                    lotes_en_conversacion += 1
                    if callback_progreso:
                        callback_progreso(min(i + tamano_lote, total_filas), total_filas, f"Lote {n_lote}/{total_lotes} procesado")
                    await asyncio.sleep(0.2); i += tamano_lote; n_lote += 1
            except Exception as err:
                if not (verificador_cancelacion and verificador_cancelacion()): raise
                if callback_log: callback_log(f"[INFO] Tarea interrumpida por cancelacion: {err}")
            finally:
                try:
                    await asyncio.wait_for(self._gestor.cerrar_navegador(), timeout=1.2)
                except Exception:
                    pass
                if todos_resultados:
                    salvaguardar_progreso_csv(todos_resultados, salida.ruta)
                estado = "cancelados" if (verificador_cancelacion and verificador_cancelacion()) else "completados"
                if estado == "completados" and hubo_error:
                    estado = "fallidos"
                ruta_final = salida.finalizar(estado)
                if estado == "completados":
                    notificar_cierre_exitoso(callback_log, ruta_final, ruta_md)
            return todos_resultados, ruta_final
