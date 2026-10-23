"""Servicio coordinador para IA General: Google Lens y Modo IA en navegador compartido."""

from __future__ import annotations

import asyncio
import csv
import logging
from pathlib import Path
from typing import Any, Callable

from procesos_ia.aplicacion.depurador_lens import registrar_depuracion_lens
from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.dominio.ficha_negocio import FichaNegocioLens
from procesos_ia.dominio.normalizador import formatear_columnas_delimitadas
from procesos_ia.infraestructura.web.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.infraestructura.web.manipulador_dom_lens import (
    abrir_modal_lens, cargar_archivo_en_lens, cargar_url_en_lens,
    esperar_vision_general_ia, extraer_enlaces_relacionados, parsear_sintesis_negocio,
)
from procesos_ia.infraestructura.web.manipulador_dom_modo_ia import (
    activar_modo_ia, enviar_prompt_modo_ia, esperar_respuesta_modo_ia, extraer_datos_estructurados_modo_ia,
)

logger = logging.getLogger(__name__)


class ServicioIAGeneral:
    """Orquestador de consultas visuales y estructuradas compartiendo sesion de Chromium."""

    def __init__(
        self, gestor_sesion: GestorSesionNodriver | None = None,
        configuracion_web: ConfiguracionWeb | None = None,
        enrutador: EnrutadorSalidas | None = None,
    ) -> None:
        self._config = configuracion_web or ConfiguracionWeb()
        self._gestor = gestor_sesion or GestorSesionNodriver(self._config)
        self._enrutador = enrutador or EnrutadorSalidas()
        self._cancelado = False

    @property
    def gestor_sesion(self) -> GestorSesionNodriver: return self._gestor

    def cancelar(self) -> None: self._cancelado = True

    async def procesar_imagen_lens(
        self, fuente_imagen: str, id_registro: str = "img_1",
        cerrar_pestana: bool = False, callback_log: Callable[[str], None] | None = None,
    ) -> FichaNegocioLens:
        """Abre una pestana de Google y analiza la imagen o URL con Google Lens."""
        self._cancelado = False
        t0 = asyncio.get_event_loop().time()
        if callback_log: callback_log("[INFO] Abriendo navegador...")
        pestana = await self._gestor.abrir_nueva_pestana("https://www.google.com")
        try:
            modal_abierto = await abrir_modal_lens(pestana)
            if not modal_abierto:
                if callback_log: callback_log("[ERROR] No se pudo abrir modal de Google Lens.")
                return FichaNegocioLens(
                    id_registro=id_registro, fuente_imagen=fuente_imagen,
                    estado_ia="ERROR_MODAL", texto_sintesis="[ERROR] No se pudo abrir modal de Google Lens",
                )

            es_url = fuente_imagen.startswith("http://") or fuente_imagen.startswith("https://")
            if callback_log: callback_log(f"[INFO] Enviando imagen a Google Lens ({'URL' if es_url else 'archivo'})...")
            if es_url:
                cargado = await cargar_url_en_lens(pestana, fuente_imagen)
            else:
                p_img = Path(fuente_imagen)
                if not p_img.is_file() and (self._enrutador.imagenes / fuente_imagen).is_file():
                    p_img = self._enrutador.imagenes / fuente_imagen
                cargado = await cargar_archivo_en_lens(pestana, p_img)

            if not cargado:
                if callback_log: callback_log("[ERROR] No se pudo ingresar imagen a Google Lens.")
                return FichaNegocioLens(
                    id_registro=id_registro, fuente_imagen=fuente_imagen,
                    estado_ia="ERROR_SUBIDA", texto_sintesis="[ERROR] No se pudo ingresar la imagen a Google Lens",
                )

            if callback_log: callback_log("[INFO] Recibiendo respuesta de IA...")
            texto_respuesta, estado_ia = await esperar_vision_general_ia(
                pestana, self._config.tiempo_espera_respuesta_segundos
            )
            if callback_log: callback_log("[INFO] Leyendo respuesta del DOM...")
            html_pagina = ""
            try:
                html_res = await pestana.evaluate("document.documentElement.outerHTML")
                html_pagina = html_res if isinstance(html_res, str) and len(html_res) > 100 else await pestana.get_content()
            except Exception: pass
            enlaces = await extraer_enlaces_relacionados(pestana)

            if callback_log: callback_log("[INFO] Sacando respuesta y estructurando datos con BeautifulSoup...")
            ficha = parsear_sintesis_negocio(
                texto=texto_respuesta, html=html_pagina, enlaces=enlaces, id_registro=id_registro, fuente_imagen=fuente_imagen,
            )
            ficha.estado_ia = estado_ia
            try:
                registrar_depuracion_lens(self._enrutador.extracciones, fuente_imagen, texto_respuesta, html_pagina, ficha)
            except Exception: pass
            dur = asyncio.get_event_loop().time() - t0
            nombre_res = ficha.negocio or ficha.propietario or "Ficha encontrada"
            if callback_log: callback_log(f"[OK] Respuesta encontrada ({dur:.1f}s, {estado_ia}): {nombre_res}")
            return ficha
        finally:
            if cerrar_pestana:
                try: await pestana.close()
                except Exception: pass

    async def procesar_carpeta_imagenes_lens(
        self, carpeta: Path,
        callback_progreso: Callable[[int, int, str], None] | None = None,
        callback_log: Callable[[str], None] | None = None,
    ) -> tuple[list[FichaNegocioLens], Path]:
        """Procesa una coleccion de imagenes de forma estrictamente individual (1 a 1)."""
        self._cancelado = False
        t_inicio = asyncio.get_event_loop().time()
        extensiones = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        archivos = [p for p in carpeta.iterdir() if p.is_file() and p.suffix.lower() in extensiones]
        total = len(archivos)
        resultados: list[FichaNegocioLens] = []
        self._enrutador.asegurar_directorios()
        ruta_salida = self._enrutador.extracciones / f"extraccion_lens_{carpeta.name}.csv"

        for idx, archivo in enumerate(archivos, start=1):
            if self._cancelado:
                if callback_log: callback_log("[INFO] Proceso cancelado por el usuario.")
                break
            if callback_progreso: callback_progreso(idx - 1, total, f"Procesando {idx}/{total}: {archivo.name}")
            if callback_log: callback_log(f"[INFO] ({idx}/{total}) Procesando imagen: {archivo.name}")
            try:
                ficha = await self.procesar_imagen_lens(
                    fuente_imagen=str(archivo), id_registro=f"img_{idx}", cerrar_pestana=True, callback_log=callback_log,
                )
            except Exception as error:
                ficha = FichaNegocioLens(id_registro=f"img_{idx}", fuente_imagen=str(archivo), texto_sintesis=f"[ERROR] {error}")
            resultados.append(ficha)
            nombre_res = ficha.negocio or ficha.propietario or "Ficha generada"
            if callback_progreso: callback_progreso(idx, total, f"Completado: {nombre_res}")
            await asyncio.sleep(0.5)

        if resultados:
            if callback_log: callback_log(f"[INFO] Guardando en el CSV: {ruta_salida.name}...")
            self._guardar_fichas_csv(resultados, ruta_salida)
            t_total = asyncio.get_event_loop().time() - t_inicio
            if callback_log: callback_log(f"[OK] Guardado en CSV: {ruta_salida.resolve()} (Tiempo total: {t_total:.1f}s)")
        await self.cerrar_navegador()
        return resultados, ruta_salida

    async def procesar_csv_con_lens(
        self, ruta_csv: Path, columna_imagen: str,
        callback_progreso: Callable[[int, int, str], None] | None = None,
        callback_log: Callable[[str], None] | None = None,
    ) -> tuple[list[FichaNegocioLens], Path]:
        """Recorre filas de un CSV y analiza la columna de imagen/URL de forma individual."""
        self._cancelado = False
        t_inicio = asyncio.get_event_loop().time()
        filas: list[dict[str, str]] = []
        with open(ruta_csv, mode="r", encoding="utf-8-sig", errors="ignore") as f:
            filas = list(csv.DictReader(f))

        total = len(filas)
        resultados: list[FichaNegocioLens] = []
        filas_enriquecidas: list[dict[str, Any]] = []

        for idx, fila in enumerate(filas, start=1):
            if self._cancelado:
                if callback_log: callback_log("[INFO] Procesamiento de CSV cancelado por el usuario.")
                break
            valor_img = fila.get(columna_imagen, "").strip()
            if callback_progreso: callback_progreso(idx - 1, total, f"Analizando fila {idx}/{total}")
            if callback_log: callback_log(f"[INFO] ({idx}/{total}) Procesando fila {idx}...")
            try:
                ficha = (
                    await self.procesar_imagen_lens(
                        fuente_imagen=valor_img, id_registro=f"fila_{idx}", cerrar_pestana=True, callback_log=callback_log,
                    ) if valor_img else FichaNegocioLens(id_registro=f"fila_{idx}", texto_sintesis="[INFO] Sin imagen")
                )
            except Exception as error:
                ficha = FichaNegocioLens(id_registro=f"fila_{idx}", texto_sintesis=f"[ERROR] {error}")

            resultados.append(ficha)
            fila_salida = dict(fila)
            fila_salida.update(ficha.a_diccionario(normalizado=True))
            filas_enriquecidas.append(fila_salida)
            nombre_res = ficha.negocio or ficha.propietario or "Fila procesada"
            if callback_progreso: callback_progreso(idx, total, f"Completado: {nombre_res}")
            await asyncio.sleep(0.5)

        self._enrutador.asegurar_directorios()
        ruta_salida = self._enrutador.extracciones / f"enriquecido_lens_{ruta_csv.stem}.csv"
        if filas_enriquecidas:
            if callback_log: callback_log(f"[INFO] Guardando en el CSV enriquecido: {ruta_salida.name}...")
            self._guardar_filas_csv(filas_enriquecidas, ruta_salida)
            t_total = asyncio.get_event_loop().time() - t_inicio
            if callback_log: callback_log(f"[OK] Guardado en CSV: {ruta_salida.resolve()} (Tiempo total: {t_total:.1f}s)")
        await self.cerrar_navegador()
        return resultados, ruta_salida

    async def procesar_modo_ia_lote(
        self,
        filas: list[dict[str, Any]],
        instrucciones: str,
        columnas: list[str] | None = None,
        tamano_lote: int = 5,
        callback_progreso: Callable[[int, int, str], None] | None = None,
        callback_log: Callable[[str], None] | None = None,
        nombre_salida: str = "evaluacion",
    ) -> tuple[list[dict[str, Any]], Path | None]:
        """Envía instrucciones y filas en lotes delimitados por '|' a Modo IA y guarda CSV."""
        self._cancelado = False
        total_filas = len(filas)
        total_lotes = (total_filas + tamano_lote - 1) // tamano_lote if total_filas > 0 else 1
        todos_resultados: list[dict[str, Any]] = []
        if callback_log:
            callback_log(f"[INFO] Iniciando Modo IA: {total_filas} filas en {total_lotes} lote(s) de {tamano_lote}")

        pestana = await self._gestor.abrir_nueva_pestana("https://www.google.com")
        await activar_modo_ia(pestana)

        for n_lote, i in enumerate(range(0, total_filas, tamano_lote), start=1):
            if self._cancelado:
                if callback_log: callback_log("[INFO] Proceso de Modo IA cancelado por el usuario.")
                break

            lote_actual = filas[i : i + tamano_lote]
            if callback_log:
                callback_log(f"[INFO] Enviando Lote {n_lote}/{total_lotes} ({len(lote_actual)} filas) con '|'...")

            lineas_datos = [
                f"[FILA {i + sub_idx}]: {formatear_columnas_delimitadas(f, columnas)}"
                for sub_idx, f in enumerate(lote_actual, start=1)
            ]
            prompt_completo = (
                f"{instrucciones}\n\nDATOS A EVALUAR:\n"
                "- Cada FILA inicia con la etiqueta '[FILA <id>]:' y termina con salto de linea.\n"
                "- Las COLUMNAS dentro de cada fila estan separadas exclusivamente por ' | '.\n\n"
                + "\n".join(lineas_datos)
                + "\n\nResponde estrictamente en formato JSON con la clave 'resultados' y el 'id' de cada fila:\n"
                "{\"resultados\": [{\"id\": 1, ...}]}"
            )
            enviado = await enviar_prompt_modo_ia(pestana, prompt_completo)
            if not enviado:
                if callback_log: callback_log(f"[ERROR] Falló envío en Lote {n_lote}")
                if callback_progreso: callback_progreso(n_lote, total_lotes, f"Lote {n_lote}/{total_lotes} (error de envío)")
                continue

            texto_resp = await esperar_respuesta_modo_ia(pestana, self._config.tiempo_espera_respuesta_segundos)
            datos = extraer_datos_estructurados_modo_ia(texto_resp)
            res_lote = datos.get("resultados", []) if isinstance(datos, dict) else (datos if isinstance(datos, list) else [])

            for idx_sub, fila in enumerate(lote_actual):
                salida = dict(fila)
                if idx_sub < len(res_lote) and isinstance(res_lote[idx_sub], dict):
                    salida.update(res_lote[idx_sub])
                elif texto_resp:
                    salida["respuesta_modo_ia"] = texto_resp
                todos_resultados.append(salida)

            if callback_log: callback_log(f"[OK] Lote {n_lote}/{total_lotes} completado.")
            if callback_progreso: callback_progreso(n_lote, total_lotes, f"Lote {n_lote}/{total_lotes} completado")
            await asyncio.sleep(0.5)

        self._enrutador.asegurar_directorios()
        ruta_salida = self._enrutador.extracciones / f"modo_ia_{nombre_salida}.csv"
        if todos_resultados:
            self._guardar_filas_csv(todos_resultados, ruta_salida)
            if callback_log: callback_log(f"[OK] Resultados consolidados en: {ruta_salida.resolve()}")
        await self.cerrar_navegador()
        return todos_resultados, ruta_salida

    async def cerrar_navegador(self) -> None:
        """Cierra el navegador Chromium y libera bloqueos."""
        try:
            await self._gestor.cerrar()
        except Exception as error:
            logger.warning("[ALERTA] Error al cerrar navegador: %s", error)

    def _guardar_fichas_csv(self, fichas: list[FichaNegocioLens], destino: Path) -> None:
        if not fichas: return
        campos = [
            "id_registro", "estado_ia", "propietario", "negocio", "categoria", "telefono",
            "sitio_web", "correo_electronico", "licencia", "ubicacion", "idiomas", "enlaces_str", "texto_sintesis", "fuente_imagen",
        ]
        with open(destino, mode="w", encoding="utf-8-sig", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
            escritor.writeheader()
            for ficha in fichas: escritor.writerow(ficha.a_diccionario(normalizado=True))

    def _guardar_filas_csv(self, filas: list[dict[str, Any]], destino: Path) -> None:
        if not filas: return
        with open(destino, mode="w", encoding="utf-8-sig", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=list(filas[0].keys()), extrasaction="ignore")
            escritor.writeheader()
            escritor.writerows(filas)
