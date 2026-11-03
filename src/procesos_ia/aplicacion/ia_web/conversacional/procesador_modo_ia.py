"""Modulo de aplicacion para evaluacion por lotes en Modo IA con conversacion estructurada."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
import re
from typing import Any

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.comun.guardador_extracciones import guardar_filas_enriquecidas_csv
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
    contar_turnos_modo_ia,
    enviar_prompt_modo_ia,
    esperar_respuesta_modo_ia,
    extraer_datos_estructurados_modo_ia,
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
        items = datos.get("resultados", [])
        if not items and "resultado" in datos:
            res_val = datos["resultado"]
            items = res_val if isinstance(res_val, list) else [res_val]
    elif isinstance(datos, list):
        items = datos

    mapa_por_posicion: dict[int, dict[str, Any]] = {}
    tamano = len(lote_actual)

    def _resolver_posicion(id_num: int) -> int | None:
        if 1 <= id_num <= tamano:
            return id_num - 1
        if indice_base <= id_num < indice_base + tamano:
            return id_num - indice_base
        return None

    # 1. Mapeo estructurado JSON si existe
    for idx_item, it in enumerate(items):
        if isinstance(it, dict):
            id_val = it.get("id") or it.get("ID") or it.get("fila")
            try:
                id_num = int(id_val) if id_val is not None else (idx_item + 1)
            except (ValueError, TypeError):
                id_num = idx_item + 1
            pos = _resolver_posicion(id_num)
            if pos is None and idx_item < tamano:
                pos = idx_item
            if pos is not None:
                campos_limpios = {
                    sanear_identificador_columna(k, "col"): v
                    for k, v in it.items()
                    if k.lower() not in ("id", "fila")
                }
                mapa_por_posicion[pos] = campos_limpios
        elif isinstance(it, str) and idx_item < tamano:
            mapa_por_posicion[idx_item] = {"evaluacion_ia": it.strip()}

    # 2. Si no hubo JSON, intentar parseo por lineas con [FILA <id>]
    if not mapa_por_posicion and texto_resp:
        for linea in texto_resp.splitlines():
            linea_limpia = linea.strip()
            if not linea_limpia:
                continue
            m = re.search(r"(?:\[FILA\s*(\d+)\]|FILA\s*(\d+)|\b(\d+))\s*[:\.\-]?\s*(.*)", linea_limpia, re.IGNORECASE)
            if m:
                id_num = int(m.group(1) or m.group(2) or m.group(3))
                val = (m.group(4) or "").strip().lstrip(":-. ")
                pos = _resolver_posicion(id_num)
                if pos is not None:
                    mapa_por_posicion[pos] = {"evaluacion_ia": val}

    # 3. Fallback: mapeo secuencial solo si no es mensaje de control
    if not mapa_por_posicion and texto_resp:
        if not re.search(r"instrucciones|comprendidas|listo para|env[ií]e el", texto_resp, re.I):
            lineas = [
                l.strip() for l in texto_resp.splitlines()
                if l.strip() and not l.strip().startswith("Respuesta") and not l.strip().startswith("```")
            ]
            if all(len(l) < 140 for l in lineas):
                for sub_i, lin in enumerate(lineas[:tamano]):
                    mapa_por_posicion[sub_i] = {"evaluacion_ia": lin}

    # Combinar con cada fila original inmutablemente
    filas_combinadas: list[dict[str, Any]] = []
    for sub_i, fila_orig in enumerate(lote_actual):
        campos_ia = mapa_por_posicion.get(sub_i, {})
        fila_comb = dict(fila_orig)
        fila_comb.update(campos_ia)
        filas_combinadas.append(fila_comb)

    return filas_combinadas


class ProcesadorModoIA:
    """Ejecuta solicitudes en Modo IA enviando instrucciones iniciales y lotes sucesivos."""

    def __init__(
        self,
        gestor_sesion: GestorSesionNodriver,
        enrutador: EnrutadorSalidas,
        configuracion: ConfiguracionWeb,
    ) -> None:
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
    ) -> tuple[list[dict[str, Any]], Path | None]:
        """Procesa registros en conversacion continua renovando contexto segun lotes_por_conversacion."""
        total_filas = len(filas)
        total_lotes = (total_filas + tamano_lote - 1) // tamano_lote if total_filas > 0 else 1
        todos_resultados, hubo_error = [], False
        if callback_log:
            callback_log(f"[INFO] Modo IA: {total_filas} filas en {total_lotes} lotes ({tamano_lote} f/lote, {lotes_por_conversacion} l/chat)")
        instrucciones_compactas = compactar_instrucciones_prompt(instrucciones)
        salida = self._enrutador.reservar_salida("modo_ia", f"modo_ia_{nombre_salida}.csv", raiz_destino=carpeta_salida)

        with salida:
            try:
                pestana = None
                lotes_en_conversacion = 0
                i = 0
                n_lote = 1
                reintentos_limite = 0

                while i < total_filas:
                    if verificador_cancelacion and verificador_cancelacion():
                        if callback_log:
                            callback_log("[INFO] Proceso de Modo IA cancelado por el usuario.")
                        break

                    lote_actual = filas[i : i + tamano_lote]
                    indice_base = i + 1

                    # Renovar conversacion si no existe o se alcanzo el cupo de lotes por chat
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

                        # Mensaje inicial: instrucciones del sistema
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

                    # Envio del lote de datos en la conversacion activa (la IA ve siempre [FILA 1..N])
                    fila_desde = i + 1
                    fila_hasta = min(i + len(lote_actual), total_filas)
                    if callback_log:
                        callback_log(f"[INFO] Enviando Lote {n_lote}/{total_lotes} (filas {fila_desde}-{fila_hasta} de {total_filas}) con '|'...")

                    mensaje_lote = construir_mensaje_lote_datos(
                        lote_filas=lote_actual,
                        columnas_seleccionadas=columnas,
                        indice_inicio=1,
                    )

                    turnos_antes = await marcar_turnos_previos_modo_ia(pestana)
                    enviado = await enviar_prompt_modo_ia(pestana, mensaje_lote)
                    if not enviado:
                        hubo_error = True
                        if callback_log:
                            callback_log(f"[ERROR] Falló envío en Lote {n_lote}")
                        continue

                    t_inicio_lote = asyncio.get_event_loop().time()
                    texto_resp = await esperar_respuesta_modo_ia(
                        pestana,
                        self._config.tiempo_espera_respuesta_segundos,
                        turnos_previos=turnos_antes,
                        filas_esperadas=len(lote_actual),
                    )
                    t_duracion = asyncio.get_event_loop().time() - t_inicio_lote

                    es_limite = bool(re.search(
                        r"alcanzaste el l[ií]mite de solicitudes|l[ií]mite de respuestas de ia|vuelve a intentarlo m[aá]s tarde|reached the limit of ai",
                        texto_resp,
                        re.IGNORECASE,
                    ))

                    if not texto_resp.strip() or re.search(r"estoy listo para procesar|env[ií]a el primer lote", texto_resp, re.I):
                        if callback_log:
                            callback_log(f"[ALERTA] Respuesta no válida en Lote {n_lote}. Reintentando espera...")
                        await asyncio.sleep(1.0)
                        continue

                    if es_limite:
                        reintentos_limite += 1
                        if callback_log:
                            callback_log(
                                f"[ALERTA] Límite de solicitudes de IA alcanzado en Google. "
                                f"Cerrando Chromium y borrando perfil temporal para reintentar Lote {n_lote} (intento {reintentos_limite}/3)..."
                            )
                        pestana = None
                        lotes_en_conversacion = 0
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
                    datos = extraer_datos_estructurados_modo_ia(texto_resp)

                    filas_lote = mapear_respuestas_lote(
                        texto_resp=texto_resp,
                        datos=datos,
                        lote_actual=lote_actual,
                        indice_base=indice_base,
                    )
                    evaluadas = sum(1 for f in filas_lote if f.get("evaluacion_ia"))
                    if callback_log and evaluadas < len(lote_actual):
                        callback_log(f"[ALERTA] Lote {n_lote} evaluó {evaluadas}/{len(lote_actual)} filas (IA omitió {len(lote_actual)-evaluadas}).")
                    todos_resultados.extend(filas_lote)
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

            finally:
                await self._gestor.cerrar_navegador()

            estado = "cancelados" if verificador_cancelacion and verificador_cancelacion() else "completados"
            if estado == "completados" and hubo_error:
                estado = "fallidos"
            return todos_resultados, salida.finalizar(estado)
