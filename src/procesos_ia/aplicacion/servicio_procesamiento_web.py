"""Servicio de procesamiento masivo tabular e imagenes para DeepSeek y Gemini Web."""

from __future__ import annotations

import asyncio
import csv
import json
import logging
from pathlib import Path
from typing import Any, Callable

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.dominio.normalizador import (
    formatear_columnas_delimitadas,
    normalizar_texto,
)
from procesos_ia.infraestructura.web.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.extractor_json import extraer_y_reparar_json
from procesos_ia.infraestructura.web.gestor_sesion_nodriver import GestorSesionNodriver
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


class ServicioProcesamientoWeb:
    """Orquesta la ejecucion real de lotes tabulares e imagenes en DeepSeek y Gemini."""

    def __init__(
        self,
        gestor_sesion: GestorSesionNodriver | None = None,
        configuracion_web: ConfiguracionWeb | None = None,
        enrutador: EnrutadorSalidas | None = None,
    ) -> None:
        self._config = configuracion_web or ConfiguracionWeb()
        self._gestor = gestor_sesion or GestorSesionNodriver(self._config)
        self._enrutador = enrutador or EnrutadorSalidas()
        self._cancelado = False
        self._consultas_chat = 0

    def cancelar(self) -> None:
        self._cancelado = True

    async def _obtener_pestana(self, motor: str) -> Any:
        url = self._config.url_gemini if motor == "gemini" else self._config.url_deepseek
        patrones = ("Gemini", "Google") if motor == "gemini" else ("DeepSeek",)
        return await self._gestor.navegar_o_reutilizar(url, patrones)

    async def _rotar_chat_si_requerido(self, pestana: Any, motor: str, limite: int) -> None:
        if limite > 0 and self._consultas_chat >= limite:
            if motor == "gemini":
                await iniciar_nuevo_chat_gemini(pestana)
            else:
                await iniciar_nuevo_chat_deepseek(pestana)
            self._consultas_chat = 0
            await asyncio.sleep(1.5)

    def _resolver_imagen(
        self,
        fila: dict[str, Any],
        col_img: str | None,
        carpeta_img: Path | None,
    ) -> Path | None:
        if not col_img and not carpeta_img:
            return None
        val = str(fila.get(col_img, "")).strip() if col_img else ""
        if val:
            ruta_directa = Path(val)
            if ruta_directa.is_file():
                return ruta_directa
            if carpeta_img and carpeta_img.is_dir():
                candidato = carpeta_img / val
                if candidato.is_file():
                    return candidato
                for ext in (".jpg", ".jpeg", ".png", ".webp"):
                    cand_ext = carpeta_img / f"{val}{ext}"
                    if cand_ext.is_file():
                        return cand_ext
        return None

    async def procesar_csv(
        self,
        motor: str,
        ruta_csv: Path,
        columnas: list[str],
        instrucciones: str,
        tamano_lote: int = 5,
        columna_imagen: str | None = None,
        carpeta_imagenes: Path | None = None,
        rotacion_chat: int = 2,
        callback_progreso: Callable[[int, int, str], None] | None = None,
        callback_log: Callable[[str], None] | None = None,
    ) -> tuple[list[dict[str, Any]], Path]:
        """Procesa registros del CSV enviando lotes de texto o imagenes 1 a 1 al navegador."""
        self._cancelado = False
        self._consultas_chat = 0
        motor = motor.lower().strip()

        filas: list[dict[str, Any]] = []
        with open(ruta_csv, mode="r", encoding="utf-8-sig", errors="ignore") as f:
            lector = csv.DictReader(f)
            filas = [dict(r) for r in lector]

        total_filas = len(filas)
        if total_filas == 0:
            raise ValueError("El archivo CSV no contiene registros para procesar.")

        pestana = await self._obtener_pestana(motor)
        if callback_log:
            callback_log(f"[INFO] Navegador conectado a {motor.upper()} para {total_filas} registros")

        # Detectar si hay flujo de imagenes (1 a 1) o de texto tabular por lotes
        primer_img = self._resolver_imagen(filas[0], columna_imagen, carpeta_imagenes)
        modo_imagen = primer_img is not None or bool(columna_imagen)

        if modo_imagen:
            return await self._procesar_flujo_imagenes(
                motor, pestana, filas, columnas, instrucciones, columna_imagen,
                carpeta_imagenes, rotacion_chat, ruta_csv.stem, callback_progreso, callback_log,
            )
        return await self._procesar_flujo_texto_lotes(
            motor, pestana, filas, columnas, instrucciones, tamano_lote,
            rotacion_chat, ruta_csv.stem, callback_progreso, callback_log,
        )

    async def procesar_carpeta_imagenes(
        self, motor: str, carpeta: Path, instrucciones: str, rotacion_chat: int = 2,
        callback_progreso: Callable | None = None, callback_log: Callable | None = None,
    ) -> tuple[list[dict[str, Any]], Path]:
        self._cancelado = False; self._consultas_chat = 0
        exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        archivos = [p for p in carpeta.iterdir() if p.is_file() and p.suffix.lower() in exts]
        if not archivos: raise ValueError(f"Sin imágenes compatibles en {carpeta}")
        filas = [{"id": i, "archivo": p.name, "ruta_archivo": str(p)} for i, p in enumerate(archivos, 1)]
        pestana = await self._obtener_pestana(motor)
        return await self._procesar_flujo_imagenes(
            motor, pestana, filas, ["archivo"], instrucciones, "ruta_archivo",
            carpeta, rotacion_chat, f"carpeta_{carpeta.name}", callback_progreso, callback_log,
        )

    async def procesar_imagen_individual(
        self, motor: str, ruta_img: Path, instrucciones: str,
        callback_progreso: Callable | None = None, callback_log: Callable | None = None,
    ) -> tuple[list[dict[str, Any]], Path]:
        if not ruta_img.is_file(): raise ValueError(f"Archivo no existe: {ruta_img}")
        filas = [{"id": 1, "archivo": ruta_img.name, "ruta_archivo": str(ruta_img)}]
        pestana = await self._obtener_pestana(motor)
        return await self._procesar_flujo_imagenes(
            motor, pestana, filas, ["archivo"], instrucciones, "ruta_archivo",
            ruta_img.parent, 0, f"individual_{ruta_img.stem}", callback_progreso, callback_log,
        )

    async def _procesar_flujo_imagenes(
        self, motor: str, pestana: Any, filas: list[dict[str, Any]],
        columnas: list[str], instrucciones: str, col_img: str | None,
        carpeta_img: Path | None, rotacion: int, stem: str,
        cb_prog: Callable | None, cb_log: Callable | None,
    ) -> tuple[list[dict[str, Any]], Path]:
        total = len(filas)
        resultados: list[dict[str, Any]] = []
        if cb_log:
            cb_log(f"[INFO] Modo visual activo en {motor.upper()}: Procesando {total} imágenes de forma individual (1 a 1)")

        for idx, fila in enumerate(filas, start=1):
            if self._cancelado:
                if cb_log: cb_log("[INFO] Procesamiento cancelado por el usuario.")
                break

            await self._rotar_chat_si_requerido(pestana, motor, rotacion)
            ruta_img = self._resolver_imagen(fila, col_img, carpeta_img)
            datos_cols = formatear_columnas_delimitadas(fila, columnas)

            prompt = (
                f"{instrucciones}\n\n"
                f"DATOS DE LA IMAGEN O REGISTRO (delimitados por '|'):\n"
                f"[FILA {idx}]: {datos_cols}\n\n"
                f"Analiza la imagen adjunta y responde estrictamente en formato JSON:\n"
                f"{{\"calificacion\": \"...\", \"motivo\": \"...\"}}"
            )

            if cb_log:
                img_desc = ruta_img.name if ruta_img else "(sin archivo)"
                cb_log(f"[INFO] Fila {idx}/{total}: Enviando imagen '{img_desc}' a {motor.upper()}...")

            enviado = (await enviar_prompt_gemini(pestana, prompt, ruta_img)) if motor == "gemini" else (await enviar_prompt_deepseek(pestana, prompt, ruta_img))
            self._consultas_chat += 1

            if not enviado:
                fila_salida = dict(fila)
                fila_salida["error_inferencia"] = "Fallo al inyectar prompt o imagen"
                resultados.append(fila_salida)
                if cb_prog: cb_prog(idx, total, f"Imagen {idx}/{total} (fallo de envío)")
                continue

            resp_txt = (await esperar_respuesta_gemini(pestana, self._config.tiempo_espera_respuesta_segundos)) if motor == "gemini" else (await esperar_respuesta_deepseek(pestana, self._config.tiempo_espera_respuesta_segundos))
            parsed = extraer_y_reparar_json(resp_txt)
            fila_salida = dict(fila)
            if isinstance(parsed, dict):
                fila_salida.update(parsed)
            else:
                fila_salida["respuesta_modelo"] = normalizar_texto(resp_txt[:400])
            resultados.append(fila_salida)
            if cb_log:
                cb_log(f"[OK] Fila {idx} completada.")
            if cb_prog: cb_prog(idx, total, f"Imagen {idx}/{total} completada")
            await asyncio.sleep(1.0)

        self._enrutador.asegurar_directorios()
        destino = self._enrutador.extracciones / f"{motor}_imagenes_{stem}.csv"
        self._guardar_csv(resultados, destino)
        return resultados, destino

    async def _procesar_flujo_texto_lotes(
        self, motor: str, pestana: Any, filas: list[dict[str, Any]],
        columnas: list[str], instrucciones: str, tamano_lote: int,
        rotacion: int, stem: str,
        cb_prog: Callable | None, cb_log: Callable | None,
    ) -> tuple[list[dict[str, Any]], Path]:
        total = len(filas)
        total_lotes = (total + tamano_lote - 1) // tamano_lote
        resultados: list[dict[str, Any]] = []

        if cb_log:
            cb_log(f"[INFO] Modo texto en {motor.upper()}: {total} filas en {total_lotes} lote(s) de {tamano_lote}")

        for n_lote, i in enumerate(range(0, total, tamano_lote), start=1):
            if self._cancelado:
                if cb_log: cb_log("[INFO] Procesamiento cancelado por el usuario.")
                break
            lote = filas[i : i + tamano_lote]
            await self._rotar_chat_si_requerido(pestana, motor, rotacion)
            lineas_datos = []
            for sub_idx, f in enumerate(lote, start=1):
                idx_glob = i + sub_idx
                lineas_datos.append(f"[FILA {idx_glob}]: {formatear_columnas_delimitadas(f, columnas)}")

            bloque_txt = "\n".join(lineas_datos)
            prompt = (
                f"{instrucciones}\n\n"
                f"DATOS A EVALUAR:\n"
                f"- Cada FILA inicia con la etiqueta '[FILA <id>]:' y termina con salto de linea.\n"
                f"- Las COLUMNAS dentro de cada fila estan separadas exclusivamente por ' | '.\n\n"
                f"{bloque_txt}\n\n"
                f"Responde estrictamente un arreglo JSON con los resultados de cada [FILA id]:\n"
                f"[{{\"id\": {i + 1}, \"calificacion\": \"...\", \"motivo\": \"...\"}}]"
            )

            if cb_log:
                cb_log(f"[INFO] Enviando Lote {n_lote}/{total_lotes} ({len(lote)} filas) a {motor.upper()}...")

            enviado = (await enviar_prompt_gemini(pestana, prompt, None)) if motor == "gemini" else (await enviar_prompt_deepseek(pestana, prompt, None))
            self._consultas_chat += 1

            if not enviado:
                for f in lote:
                    sal = dict(f); sal["error_inferencia"] = "Fallo de envio"
                    resultados.append(sal)
                if cb_prog: cb_prog(n_lote, total_lotes, f"Lote {n_lote}/{total_lotes} (fallo de envío)")
                continue

            resp_txt = (await esperar_respuesta_gemini(pestana, self._config.tiempo_espera_respuesta_segundos)) if motor == "gemini" else (await esperar_respuesta_deepseek(pestana, self._config.tiempo_espera_respuesta_segundos))
            parsed = extraer_y_reparar_json(resp_txt)
            items_res = parsed if isinstance(parsed, list) else (parsed.get("resultados", []) if isinstance(parsed, dict) else [])

            for sub_idx, f in enumerate(lote):
                sal = dict(f)
                if sub_idx < len(items_res) and isinstance(items_res[sub_idx], dict):
                    sal.update(items_res[sub_idx])
                elif resp_txt:
                    sal["respuesta_modelo"] = normalizar_texto(resp_txt[:300])
                resultados.append(sal)

            if cb_log:
                cb_log(f"[OK] Lote {n_lote}/{total_lotes} completado.")
            if cb_prog: cb_prog(n_lote, total_lotes, f"Lote {n_lote}/{total_lotes} completado")
            await asyncio.sleep(1.0)

        self._enrutador.asegurar_directorios()
        destino = self._enrutador.extracciones / f"{motor}_evaluacion_{stem}.csv"
        self._guardar_csv(resultados, destino)
        return resultados, destino

    def _guardar_csv(self, filas: list[dict[str, Any]], destino: Path) -> None:
        if not filas:
            return
        campos = list(filas[0].keys())
        with open(destino, mode="w", encoding="utf-8-sig", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
            escritor.writeheader()
            escritor.writerows(filas)
