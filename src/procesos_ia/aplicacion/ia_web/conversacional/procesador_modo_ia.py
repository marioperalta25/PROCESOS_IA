"""Modulo de aplicacion para evaluacion por lotes en Modo IA con delimitador pipe."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.comun.guardador_extracciones import guardar_filas_enriquecidas_csv
from procesos_ia.aplicacion.ia_web.conversacional.formateador_lotes_chat import (
    construir_prompt_lote_chat,
)
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.infraestructura.web.conversacional.manipulador_dom_modo_ia import (
    activar_modo_ia,
    enviar_prompt_modo_ia,
    esperar_respuesta_modo_ia,
    extraer_datos_estructurados_modo_ia,
)


class ProcesadorModoIA:
    """Ejecuta solicitudes por lotes hacia Modo IA en Google con formato delimitado por '|'."""

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
        callback_progreso: Callable[[int, int, str], None] | None = None,
        callback_log: Callable[[str], None] | None = None,
        nombre_salida: str = "evaluacion",
        carpeta_salida: Path | None = None,
        verificador_cancelacion: Callable[[], bool] | None = None,
    ) -> tuple[list[dict[str, Any]], Path | None]:
        """Envía instrucciones y filas en lotes delimitados a Modo IA y almacena el resultado."""
        total_filas = len(filas)
        total_lotes = (total_filas + tamano_lote - 1) // tamano_lote if total_filas > 0 else 1
        todos_resultados: list[dict[str, Any]] = []
        hubo_error = False

        if callback_log:
            callback_log(f"[INFO] Iniciando Modo IA: {total_filas} filas en {total_lotes} lote(s) de {tamano_lote}")

        salida = self._enrutador.reservar_salida(
            "modo_ia", f"modo_ia_{nombre_salida}.csv", raiz_destino=carpeta_salida,
        )
        with salida:
            try:
                pestana = await self._gestor.abrir_nueva_pestana("https://www.google.com")
                await activar_modo_ia(pestana)

                for n_lote, i in enumerate(range(0, total_filas, tamano_lote), start=1):
                    if verificador_cancelacion and verificador_cancelacion():
                        if callback_log:
                            callback_log("[INFO] Proceso de Modo IA cancelado por el usuario.")
                        break

                    lote_actual = filas[i : i + tamano_lote]
                    if callback_log:
                        callback_log(f"[INFO] Enviando Lote {n_lote}/{total_lotes} ({len(lote_actual)} filas) con '|'...")

                    prompt_completo = construir_prompt_lote_chat(
                        instrucciones=instrucciones,
                        lote_filas=lote_actual,
                        columnas_seleccionadas=columnas,
                        indice_inicio=i + 1,
                    )

                    enviado = await enviar_prompt_modo_ia(pestana, prompt_completo)
                    if not enviado:
                        hubo_error = True
                        if callback_log:
                            callback_log(f"[ERROR] Falló envío en Lote {n_lote}")
                        continue

                    texto_resp = await esperar_respuesta_modo_ia(pestana, self._config.tiempo_espera_respuesta_segundos)
                    datos = extraer_datos_estructurados_modo_ia(texto_resp)
                    items = datos.get("resultados", [])
                    for sub_i, fila_orig in enumerate(lote_actual):
                        item_eval = items[sub_i] if sub_i < len(items) else {}
                        fila_comb = dict(fila_orig)
                        fila_comb.update(item_eval)
                        todos_resultados.append(fila_comb)

                    if callback_progreso:
                        callback_progreso(min(i + tamano_lote, total_filas), total_filas, f"Lote {n_lote}/{total_lotes} procesado")
                    await asyncio.sleep(1.0)

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
