"""Modulo de aplicacion para evaluacion por lotes en Modo IA con conversacion estructurada."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
import re
from typing import Any

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.comun.trabajo_tabular import TrabajoTabular
from procesos_ia.aplicacion.comun.identidad_tabular import IdentidadTabular
from procesos_ia.aplicacion.ia_web.conversacional.mapeo_respuestas_tabulares import mapear_respuestas_lote
from procesos_ia.aplicacion.ia_web.comun.diagnostico_lotes import (
    detectar_limite_cuota, evaluar_calidad_lote, notificar_alerta_confirmacion_inicio,
    notificar_balance_lote, notificar_cierre_exitoso, notificar_envio_lote,
    notificar_envio_prompt_sistema, notificar_fallo_envio_lote,
    notificar_fallo_prompt_sistema, notificar_inicio_proceso,
    notificar_limite_cuota, notificar_limite_persistente,
    notificar_reintento_lote, notificar_respuesta_lote,
)
from procesos_ia.aplicacion.ia_web.comun.gestor_resiliencia_web import (
    esperar_restablecimiento_conexion, recuperar_si_captcha_google, verificar_conexion_internet,
)
from procesos_ia.aplicacion.ia_web.comun.guardador_extracciones import (
    guardar_auditoria_modo_ia_md, guardar_filas_enriquecidas_csv,
)
from procesos_ia.aplicacion.ia_web.conversacional.formateador_lotes_chat import (
    compactar_instrucciones_prompt, construir_mensaje_lote_datos,
    construir_prompt_inicial_conversacion,
)
from procesos_ia.dominio.reanudacion import EstadoIA
from procesos_ia.dominio.excepciones import ErrorPersistenciaTabular
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.infraestructura.web.conversacional.manipulador_dom_modo_ia import (
    activar_modo_ia, enviar_prompt_modo_ia, esperar_respuesta_modo_ia,
    extraer_datos_estructurados_modo_ia, extraer_html_ultimo_turno,
    marcar_turnos_previos_modo_ia,
)


class ProcesadorModoIA:
    """Ejecuta solicitudes en Modo IA con conversacion continua, resiliencia y salvaguarda."""

    def __init__(self, gestor_sesion: GestorSesionNodriver, enrutador: EnrutadorSalidas, configuracion: ConfiguracionWeb) -> None:
        self._gestor = gestor_sesion
        self._enrutador = enrutador
        self._config = configuracion

    async def _manejar_captcha(self, pestana: Any, reintentos_captcha: int, callback_log: Any) -> tuple[bool, int]:
        """Detecta CAPTCHA de Google, reinicia con perfil limpio + 2s y controla el limite de reintentos."""
        if not await recuperar_si_captcha_google(pestana, self._gestor, callback_log):
            return False, reintentos_captcha
        reintentos_captcha += 1
        if reintentos_captcha > 3 and callback_log:
            callback_log("[ERROR] CAPTCHA persistente tras 3 reinicios de perfil. Deteniendo proceso.")
        return True, reintentos_captcha

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
        trabajo_tabular: TrabajoTabular | None = None,
    ) -> tuple[list[dict[str, Any]], Path | None]:
        """Procesa registros en conversacion continua renovando contexto segun lotes_por_conversacion."""
        trabajo = trabajo_tabular or TrabajoTabular(
            filas, IdentidadTabular.crear(None, "modo_ia", filas, instrucciones, columnas),
        )
        filas = trabajo.filas_pendientes
        total_filas = len(filas)
        total_lotes = (total_filas + tamano_lote - 1) // tamano_lote if total_filas > 0 else 1
        todos_resultados = []
        notificar_inicio_proceso(callback_log, "Modo IA de Google", total_filas, total_lotes, tamano_lote, lotes_por_conversacion)
        instrucciones_compactas = compactar_instrucciones_prompt(instrucciones)
        with trabajo.abrir(self._enrutador, f"modo_ia_{nombre_salida}.csv", carpeta_salida, salida_existente) as salida:
            if trabajo.solo_exportar:
                return [], trabajo.finalizar("completados", guardar_filas_enriquecidas_csv)
            if trabajo.respaldo:
                trabajo.notificar_progreso(callback_progreso, 0, trabajo.parametros["progreso_recuperado"])
            ruta_md = salida.ruta.with_suffix(".md") if generar_auditoria_md else None
            if ruta_md and not ruta_md.exists():
                guardar_auditoria_modo_ia_md(ruta_md, 0, total_lotes, 0, 0, "", "", prompt_inicial=instrucciones_compactas)
            try:
                pestana = None
                lotes_en_conversacion = i = reintentos_limite = reintentos_lote = reintentos_invalidos = reintentos_captcha = 0
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
                            aviso_v = getattr(self._gestor, "ultimo_aviso_ventana", None)
                            if aviso_v and callback_log: callback_log(f"[ALERTA] {aviso_v}")
                        await activar_modo_ia(pestana); lotes_en_conversacion = 0
                        hubo_captcha, reintentos_captcha = await self._manejar_captcha(pestana, reintentos_captcha, callback_log)
                        if hubo_captcha:
                            pestana = None
                            if reintentos_captcha > 3: break
                            continue
                        if verificador_cancelacion and verificador_cancelacion(): break
                        notificar_envio_prompt_sistema(callback_log, len(instrucciones_compactas))
                        prompt_inicial = construir_prompt_inicial_conversacion(instrucciones_compactas, columnas_seleccionadas=columnas, tamano_lote=tamano_lote)
                        turnos_inicio = await marcar_turnos_previos_modo_ia(pestana)
                        enviado_inicial = await enviar_prompt_modo_ia(pestana, prompt_inicial)
                        if not enviado_inicial:
                            hubo_captcha, reintentos_captcha = await self._manejar_captcha(pestana, reintentos_captcha, callback_log)
                            if hubo_captcha:
                                pestana, lotes_en_conversacion = None, 0
                                if reintentos_captcha > 3: break
                                continue
                            notificar_fallo_prompt_sistema(callback_log); pestana = None; await asyncio.sleep(0.5); continue
                        resp_inicio = await esperar_respuesta_modo_ia(
                            pestana, self._config.tiempo_espera_respuesta_segundos, turnos_previos=turnos_inicio,
                            verificador_cancelacion=verificador_cancelacion,
                        )
                        if not resp_inicio.strip():
                            hubo_captcha, reintentos_captcha = await self._manejar_captcha(pestana, reintentos_captcha, callback_log)
                            if hubo_captcha:
                                pestana, lotes_en_conversacion = None, 0
                                if reintentos_captcha > 3: break
                                continue
                            notificar_alerta_confirmacion_inicio(callback_log); pestana = None; continue
                        await asyncio.sleep(0.3)

                    if verificador_cancelacion and verificador_cancelacion(): break
                    fila_desde, fila_hasta = i + 1, min(i + len(lote_actual), total_filas)
                    notificar_envio_lote(callback_log, n_lote, total_lotes, fila_desde, fila_hasta, total_filas, delimitador="|")
                    mensaje_lote = construir_mensaje_lote_datos(lote_filas=lote_actual, columnas_seleccionadas=columnas, indice_inicio=1)
                    turnos_antes = await marcar_turnos_previos_modo_ia(pestana)
                    enviado = await enviar_prompt_modo_ia(pestana, mensaje_lote)
                    if not enviado:
                        hubo_captcha, reintentos_captcha = await self._manejar_captcha(pestana, reintentos_captcha, callback_log)
                        if hubo_captcha:
                            pestana, lotes_en_conversacion = None, 0
                            if reintentos_captcha > 3: break
                            continue
                        notificar_fallo_envio_lote(callback_log, n_lote); continue
                    if verificador_cancelacion and verificador_cancelacion(): break

                    t_inicio_lote = asyncio.get_running_loop().time()
                    texto_resp = await esperar_respuesta_modo_ia(
                        pestana, self._config.tiempo_espera_respuesta_segundos,
                        turnos_previos=turnos_antes, filas_esperadas=len(lote_actual),
                        verificador_cancelacion=verificador_cancelacion,
                    )
                    t_duracion = asyncio.get_running_loop().time() - t_inicio_lote
                    if verificador_cancelacion and verificador_cancelacion(): break

                    if not texto_resp.strip() or re.search(r"estoy listo para procesar|env[ií]a el primer lote", texto_resp, re.I):
                        hubo_captcha, reintentos_captcha = await self._manejar_captcha(pestana, reintentos_captcha, callback_log)
                        if hubo_captcha:
                            pestana, lotes_en_conversacion = None, 0
                            if reintentos_captcha > 3: break
                            continue
                        reintentos_invalidos += 1
                        if reintentos_invalidos <= 2:
                            if callback_log: callback_log(f"[ALERTA] Respuesta no válida en Lote {n_lote}. Renovando sesión ({reintentos_invalidos}/2)...")
                            pestana, lotes_en_conversacion = None, 0; await asyncio.sleep(1.0); continue
                        if callback_log: callback_log(f"[ERROR] Lote {n_lote} sin respuesta válida tras 2 reintentos. Marcando filas como fallidas.")
                        filas_fallo = mapear_respuestas_lote(texto_resp="", datos=None, lote_actual=lote_actual, indice_base=indice_base)
                        for f in filas_fallo: f["_estado_ia"], f["_motivo_estado"] = EstadoIA.FALLIDO.value, "[FALLIDO] Sin respuesta valida"
                        trabajo.confirmar(filas_fallo); todos_resultados.extend(filas_fallo)
                        reintentos_invalidos = 0; pestana, lotes_en_conversacion = None, 0
                        trabajo.notificar_progreso(callback_progreso, min(i + tamano_lote, total_filas), f"Lote {n_lote}/{total_lotes} sin respuesta")
                        i += tamano_lote; n_lote += 1; continue
                    reintentos_invalidos = 0

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
                    if evaluadas < len(lote_actual):
                        if reintentos_lote < 2:
                            reintentos_lote += 1
                            if callback_log: callback_log(f"[ALERTA] Lote {n_lote} incompleto ({evaluadas}/{len(lote_actual)}). Descartando lote y reiniciando perfil limpio ({reintentos_lote}/2)...")
                            await self._gestor.reiniciar_con_perfil_limpio()
                            pestana, lotes_en_conversacion = None, 0; await asyncio.sleep(1.0); continue
                        if callback_log: callback_log(f"[ERROR] Lote {n_lote} incompleto ({evaluadas}/{len(lote_actual)}) tras 2 reinicios. Marcando lote como fallido.")
                        for f in filas_lote: f["_estado_ia"], f["_motivo_estado"] = EstadoIA.FALLIDO.value, f"[FALLIDO] Lote incompleto ({evaluadas}/{len(lote_actual)})"
                        reintentos_lote = reintentos_captcha = 0
                        trabajo.confirmar(filas_lote); todos_resultados.extend(filas_lote)
                        pestana, lotes_en_conversacion = None, 0
                        trabajo.notificar_progreso(callback_progreso, min(i + tamano_lote, total_filas), f"Lote {n_lote}/{total_lotes} incompleto")
                        i += tamano_lote; n_lote += 1; continue
                    reintentos_lote = reintentos_captcha = 0
                    notificar_balance_lote(callback_log, n_lote, evaluadas, len(lote_actual))
                    trabajo.confirmar(filas_lote)
                    todos_resultados.extend(filas_lote)
                    lotes_en_conversacion += 1
                    trabajo.notificar_progreso(callback_progreso, min(i + tamano_lote, total_filas), f"Lote {n_lote}/{total_lotes} procesado")
                    await asyncio.sleep(0.2); i += tamano_lote; n_lote += 1
            except (ErrorPersistenciaTabular, ValueError):
                raise
            except (Exception, asyncio.CancelledError) as err:
                if not (verificador_cancelacion and verificador_cancelacion()): raise
                if callback_log: callback_log(f"[INFO] Tarea interrumpida por cancelacion: {err}")
            finally:
                try:
                    await asyncio.wait_for(self._gestor.cerrar_navegador(), timeout=1.2)
                except Exception:
                    pass
            estado = "cancelados" if (verificador_cancelacion and verificador_cancelacion()) else "completados"
            ruta_final = trabajo.finalizar(estado, guardar_filas_enriquecidas_csv)
            if salida.estado == "completados":
                notificar_cierre_exitoso(callback_log, ruta_final, ruta_final.with_suffix(".md") if ruta_md else None)
            return todos_resultados, ruta_final
