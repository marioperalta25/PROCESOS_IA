"""Servicio de inferencia web que implementa ServicioInferenciaProtocol."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
import logging
from pathlib import Path
from typing import Any

from procesos_ia.aplicacion.contratos import ServicioInferenciaProtocol
from procesos_ia.dominio.modelos import ConfiguracionTrabajo, RegistroEntrada
from procesos_ia.dominio.normalizador import normalizar_datos_modelo
from procesos_ia.infraestructura.web.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.infraestructura.web.extractor_json import extraer_y_reparar_json
from procesos_ia.infraestructura.web.manipulador_dom_deepseek import (
    enviar_prompt_deepseek,
    esperar_respuesta_deepseek,
    iniciar_nuevo_chat_deepseek,
)
from procesos_ia.infraestructura.web.manipulador_dom_gemini import (
    enviar_prompt_gemini,
    esperar_respuesta_gemini,
    iniciar_nuevo_chat_gemini,
)

logger = logging.getLogger(__name__)


class ServicioInferenciaWeb:
    """Implementa ServicioInferenciaProtocol mediante automatización web."""

    def __init__(
        self,
        tipo_motor: str = "gemini",
        gestor_sesion: GestorSesionNodriver | None = None,
        configuracion_web: ConfiguracionWeb | None = None,
    ) -> None:
        self._tipo_motor = tipo_motor.lower().strip()
        self._config = configuracion_web or ConfiguracionWeb()
        self._gestor = gestor_sesion or GestorSesionNodriver(self._config)
        self._consultas_chat_actual = 0

    @property
    def tipo_motor(self) -> str:
        return self._tipo_motor

    def procesar_lote(
        self,
        lote: list[RegistroEntrada],
        configuracion: ConfiguracionTrabajo,
    ) -> list[dict[str, Any]]:
        """Ejecuta el procesamiento del lote en el navegador y correlaciona por ID."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # En hilos con event loop activo, usamos una tarea o runner
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    futuro = executor.submit(
                        asyncio.run,
                        self._procesar_lote_asincrono(lote, configuracion),
                    )
                    return futuro.result()
            return loop.run_until_complete(
                self._procesar_lote_asincrono(lote, configuracion)
            )
        except RuntimeError:
            return asyncio.run(
                self._procesar_lote_asincrono(lote, configuracion)
            )

    async def _procesar_lote_asincrono(
        self,
        lote: list[RegistroEntrada],
        configuracion: ConfiguracionTrabajo,
    ) -> list[dict[str, Any]]:
        contrato = configuracion.obtener_contrato()
        configuracion.validar_esquema_salida()
        esquema = contrato.esquema_json()
        evaluaciones = [asdict(r) for r in contrato.resultados]

        url_destino = self._config.url_gemini if self._tipo_motor == "gemini" else self._config.url_deepseek
        patrones = ("Gemini", "Google Chrome") if self._tipo_motor == "gemini" else ("DeepSeek",)
        pestana = await self._gestor.navegar_o_reutilizar(url_destino, patrones)

        # Regla: las imagenes NUNCA van por lotes; si hay imagenes o modo individual, procesar 1 a 1
        hay_imagenes = any(
            self._detectar_ruta_imagen(e.datos_para_modelo, configuracion.carpeta_imagenes) is not None
            for e in lote
        )
        if hay_imagenes or configuracion.modo_procesamiento == "individual":
            return await self._procesar_individual(pestana, lote, configuracion, contrato, esquema, evaluaciones)
        return await self._procesar_lote_tabular(pestana, lote, configuracion, contrato, esquema, evaluaciones)

    async def _rotar_chat_si_requerido(self, pestana: Any, limite_rotacion: int) -> None:
        if self._consultas_chat_actual >= limite_rotacion:
            if self._tipo_motor == "gemini":
                await iniciar_nuevo_chat_gemini(pestana)
            else:
                await iniciar_nuevo_chat_deepseek(pestana)
            self._consultas_chat_actual = 0

    async def _enviar_y_esperar(self, pestana: Any, prompt: str, ruta_img: Path | None) -> str | None:
        if self._tipo_motor == "gemini":
            exito = await enviar_prompt_gemini(pestana, prompt, ruta_img)
            return await esperar_respuesta_gemini(
                pestana, tiempo_limite=self._config.tiempo_espera_respuesta_segundos,
                intervalo_estabilidad=self._config.tiempo_estabilidad_segundos,
            ) if exito else None
        exito = await enviar_prompt_deepseek(pestana, prompt, ruta_img)
        return await esperar_respuesta_deepseek(
            pestana, tiempo_limite=self._config.tiempo_espera_respuesta_segundos,
            intervalo_estabilidad=self._config.tiempo_estabilidad_segundos,
        ) if exito else None

    async def _procesar_individual(
        self, pestana: Any, lote: list[RegistroEntrada],
        configuracion: ConfiguracionTrabajo, contrato: Any, esquema: dict, evaluaciones: list,
    ) -> list[dict[str, Any]]:
        respuestas: list[dict[str, Any]] = []
        rotacion = configuracion.rotacion_chat_cada or self._config.max_consultas_por_chat
        for entrada in lote:
            await self._rotar_chat_si_requerido(pestana, rotacion)
            try:
                datos_del = contrato.preparar_datos_delimitados(entrada.datos_para_modelo)
            except KeyError:
                respuestas.append({"identificador": entrada.identificador, "error_configuracion": "Columnas faltantes"})
                continue

            ruta_img = self._detectar_ruta_imagen(entrada.datos_para_modelo, configuracion.carpeta_imagenes)
            texto_entradas = "\n".join(f"- {k}: {v}" for k, v in datos_del.items())
            aviso = ("ATENCION: Se adjunta imagen para evaluacion visual individual.\n\n" if ruta_img else "")
            prompt = (
                f"{aviso}Analiza los siguientes datos y devuelve UNICAMENTE un objeto JSON con la estructura solicitada.\n\n"
                f"REGLAS Y CRITERIOS DE EVALUACION:\n{configuracion.prompt_sistema}\n\n"
                f"EVALUACIONES REQUERIDAS:\n{json.dumps(evaluaciones, ensure_ascii=False, indent=2)}\n\n"
                f"DATOS DE ENTRADA (columnas delimitadas por ' | '):\n{texto_entradas}\n\n"
                f"ESTRUCTURA JSON REQUERIDA:\n{json.dumps(esquema, ensure_ascii=False, indent=2)}\n\n"
                f"RESPONDE SOLO EL JSON, SIN TEXTO ADICIONAL."
            )
            salida = await self._enviar_y_esperar(pestana, prompt, ruta_img)
            self._consultas_chat_actual += 1
            if not salida:
                respuestas.append({"identificador": entrada.identificador, "error_inferencia": "Tiempo de espera agotado"})
                continue
            parsed = extraer_y_reparar_json(salida)
            if not isinstance(parsed, dict):
                respuestas.append({"identificador": entrada.identificador, "error_formato": f"JSON no valido: {salida[:120]}"})
                continue
            errs = contrato.validar_salida(parsed)
            if errs:
                respuestas.append({"identificador": entrada.identificador, "error_formato": "; ".join(errs)})
            else:
                respuestas.append({"identificador": entrada.identificador, **parsed})
        return respuestas

    async def _procesar_lote_tabular(
        self, pestana: Any, lote: list[RegistroEntrada],
        configuracion: ConfiguracionTrabajo, contrato: Any, esquema: dict, evaluaciones: list,
    ) -> list[dict[str, Any]]:
        rotacion = configuracion.rotacion_chat_cada or self._config.max_consultas_por_chat
        await self._rotar_chat_si_requerido(pestana, rotacion)
        lineas_registros = []
        for e in lote:
            datos_del = contrato.preparar_datos_delimitados(e.datos_para_modelo)
            cols_txt = " | ".join(f"{k}: {v}" for k, v in datos_del.items())
            lineas_registros.append(f"[FILA {e.identificador}]: {cols_txt}")
        bloque_lote = "\n".join(lineas_registros)

        prompt = (
            f"Analiza el siguiente lote de registros tabulares y devuelve UNICAMENTE un arreglo JSON (lista de objetos),\n"
            f"donde cada objeto corresponda a un registro evaluado preservando su identificador.\n\n"
            f"REGLAS Y CRITERIOS DE EVALUACION:\n{configuracion.prompt_sistema}\n\n"
            f"EVALUACIONES REQUERIDAS POR REGISTRO:\n{json.dumps(evaluaciones, ensure_ascii=False, indent=2)}\n\n"
            f"REGISTROS A EVALUAR (Filas por linea '[FILA id]:', columnas delimitadas por ' | '):\n{bloque_lote}\n\n"
            f"ESTRUCTURA JSON ESTRICTA REQUERIDA (Arreglo de objetos con 'identificador'):\n"
            f"[\n  {{\"identificador\": \"ID_REGISTRO\", ...campos evaluados...}}\n]\n\n"
            f"RESPONDE SOLO EL ARREGLO JSON CON TODOS LOS REGISTROS, SIN TEXTO ADICIONAL."
        )
        salida = await self._enviar_y_esperar(pestana, prompt, None)
        self._consultas_chat_actual += 1
        if not salida:
            return [{"identificador": e.identificador, "error_inferencia": "Tiempo de espera agotado"} for e in lote]

        parsed = extraer_y_reparar_json(salida)
        mapa_salidas: dict[str, dict[str, Any]] = {}
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict) and "identificador" in item:
                    mapa_salidas[str(item["identificador"])] = item
        elif isinstance(parsed, dict):
            if len(lote) == 1:
                mapa_salidas[lote[0].identificador] = parsed
            elif "identificador" in parsed:
                mapa_salidas[str(parsed["identificador"])] = parsed

        respuestas: list[dict[str, Any]] = []
        for e in lote:
            if e.identificador in mapa_salidas:
                salida_dict = {k: v for k, v in mapa_salidas[e.identificador].items() if k != "identificador"}
                errs = contrato.validar_salida(salida_dict)
                if errs:
                    respuestas.append({"identificador": e.identificador, "error_formato": "; ".join(errs)})
                else:
                    respuestas.append({"identificador": e.identificador, **salida_dict})
            else:
                respuestas.append({"identificador": e.identificador, "error_formato": "Registro omitido por el modelo en el lote"})
        return respuestas

    def _detectar_ruta_imagen(
        self,
        datos: dict[str, Any],
        carpeta_imagenes: Path | None = None,
    ) -> Path | None:
        """Identifica si algun campo contiene la ruta o nombre de una imagen valida."""
        extensiones = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
        for valor in datos.values():
            if not isinstance(valor, str):
                continue
            nombre_limpio = valor.strip()
            candidato = Path(nombre_limpio)
            if candidato.is_file():
                return candidato
            if carpeta_imagenes and carpeta_imagenes.is_dir():
                en_carpeta = carpeta_imagenes / candidato.name
                if en_carpeta.is_file():
                    return en_carpeta
                if not any(nombre_limpio.lower().endswith(ext) for ext in extensiones):
                    for ext in extensiones:
                        intento = carpeta_imagenes / f"{candidato.name}{ext}"
                        if intento.is_file():
                            return intento
            if nombre_limpio.lower().endswith(extensiones) and candidato.is_file():
                return candidato
        return None

    def cerrar(self) -> None:
        """Cierra el navegador y limpia recursos."""
        try:
            asyncio.run(self._gestor.cerrar())
        except Exception:
            pass
