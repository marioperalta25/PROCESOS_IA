"""Servicio coordinador para IA General: delega en subservicios especializados."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.conversacional.procesador_modo_ia import ProcesadorModoIA
from procesos_ia.aplicacion.ia_web.visual_1a1.procesador_archivo_urls import ProcesadorArchivoUrls
from procesos_ia.aplicacion.ia_web.visual_1a1.procesador_carpeta_imagenes import ProcesadorCarpetaImagenes
from procesos_ia.aplicacion.ia_web.visual_1a1.procesador_url_individual import ProcesadorUrlIndividual
from procesos_ia.dominio.ia_web.ficha_negocio import FichaNegocioLens
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.infraestructura.web.visual_1a1.manipulador_dom_lens import (
    abrir_modal_lens,
    cargar_archivo_en_lens,
    cargar_url_en_lens,
    esperar_vision_general_ia,
    extraer_enlaces_relacionados,
    parsear_sintesis_negocio,
)

logger = logging.getLogger(__name__)


class ServicioIAGeneral:
    """Orquestador de consultas visuales y estructuradas compartiendo sesion de Chromium."""

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
        self.ultima_salida: Path | None = None

        self._procesador_url = ProcesadorUrlIndividual(
            self._gestor, self._enrutador, self._config, self.procesar_imagen_lens
        )
        self._procesador_archivo = ProcesadorArchivoUrls(
            self._gestor, self._enrutador, self._config, self.procesar_imagen_lens
        )
        self._procesador_carpeta = ProcesadorCarpetaImagenes(
            self._gestor, self._enrutador, self._config, self.procesar_imagen_lens
        )
        self._procesador_modo_ia = ProcesadorModoIA(
            self._gestor, self._enrutador, self._config
        )

    @property
    def gestor_sesion(self) -> GestorSesionNodriver:
        return self._gestor

    @property
    def enrutador(self) -> EnrutadorSalidas:
        return self._enrutador

    def cancelar(self) -> None:
        self._cancelado = True

    async def cerrar_navegador(self) -> None:
        """Cierra el navegador y limpia la sesion activa."""
        await self._gestor.cerrar_navegador()

    def _guardar_fichas_csv(self, fichas: list[FichaNegocioLens], ruta_salida: Path) -> Path:
        """Compatibilidad para persistencia en lote de fichas de negocio."""
        from procesos_ia.aplicacion.ia_web.comun.guardador_extracciones import guardar_fichas_lote_csv
        return guardar_fichas_lote_csv(fichas, ruta_salida)

    async def procesar_imagen_lens(
        self,
        fuente_imagen: str,
        id_registro: str = "img_1",
        cerrar_pestana: bool = False,
        callback_log: Callable[[str], None] | None = None,
    ) -> FichaNegocioLens:
        """Abre una pestana de Google y analiza la imagen o URL con Google Lens."""
        if self._cancelado:
            return FichaNegocioLens(id_registro=id_registro, fuente_imagen=fuente_imagen, estado_ia="CANCELADO", texto_sintesis="[INFO] Proceso cancelado")
        t0 = asyncio.get_event_loop().time()
        if callback_log:
            callback_log("[INFO] Abriendo navegador...")
        pestana = await self._gestor.abrir_nueva_pestana("https://www.google.com")
        try:
            if self._cancelado:
                return FichaNegocioLens(id_registro=id_registro, fuente_imagen=fuente_imagen, estado_ia="CANCELADO", texto_sintesis="[INFO] Proceso cancelado")
            modal_abierto = await abrir_modal_lens(pestana)
            if not modal_abierto:
                if callback_log:
                    callback_log("[ERROR] No se pudo abrir modal de Google Lens.")
                return FichaNegocioLens(id_registro=id_registro, fuente_imagen=fuente_imagen, estado_ia="ERROR_MODAL", texto_sintesis="[ERROR] No se pudo abrir modal de Google Lens")

            es_url = fuente_imagen.startswith("http://") or fuente_imagen.startswith("https://")
            if callback_log:
                callback_log(f"[INFO] Enviando imagen a Google Lens ({'URL' if es_url else 'archivo'})...")
            if es_url:
                cargado = await cargar_url_en_lens(pestana, fuente_imagen)
            else:
                p_img = Path(fuente_imagen)
                if not p_img.is_file() and (self._enrutador.imagenes / fuente_imagen).is_file():
                    p_img = self._enrutador.imagenes / fuente_imagen
                cargado = await cargar_archivo_en_lens(pestana, p_img)

            if not cargado:
                if callback_log:
                    callback_log("[ERROR] No se pudo ingresar imagen a Google Lens.")
                return FichaNegocioLens(id_registro=id_registro, fuente_imagen=fuente_imagen, estado_ia="ERROR_SUBIDA", texto_sintesis="[ERROR] No se pudo ingresar la imagen a Google Lens")

            if callback_log:
                callback_log("[INFO] Recibiendo respuesta de IA...")
            texto_respuesta, estado_ia = await esperar_vision_general_ia(
                pestana, self._config.tiempo_espera_respuesta_segundos, verificador_cancelacion=lambda: self._cancelado
            )
            if estado_ia == "CANCELADO":
                return FichaNegocioLens(id_registro=id_registro, fuente_imagen=fuente_imagen, estado_ia="CANCELADO", texto_sintesis="[INFO] Proceso cancelado por el usuario")
            if callback_log:
                callback_log("[INFO] Leyendo respuesta del DOM...")
            html_pagina = ""
            try:
                html_res = await pestana.evaluate("document.documentElement.outerHTML")
                html_pagina = html_res if isinstance(html_res, str) and len(html_res) > 100 else await pestana.get_content()
            except Exception:
                pass
            enlaces = await extraer_enlaces_relacionados(pestana)

            if callback_log:
                callback_log("[INFO] Sacando respuesta y estructurando datos con BeautifulSoup...")
            ficha = parsear_sintesis_negocio(
                texto=texto_respuesta, html=html_pagina, enlaces=enlaces, id_registro=id_registro, fuente_imagen=fuente_imagen,
            )
            ficha.estado_ia = estado_ia
            if html_pagina:
                ficha.metadatos_adicionales["html_completo"] = html_pagina
            dur = asyncio.get_event_loop().time() - t0
            nombre_res = ficha.negocio or ficha.propietario or "Ficha encontrada"
            if callback_log:
                callback_log(f"[OK] Respuesta encontrada ({dur:.1f}s, {estado_ia}): {nombre_res}")
            return ficha
        finally:
            if cerrar_pestana:
                try:
                    await pestana.close()
                except Exception:
                    pass

    async def procesar_url_individual(
        self,
        fuente_imagen: str,
        id_registro: str = "img_1",
        carpeta_salida: Path | None = None,
        cerrar_navegador_al_terminar: bool = True,
        callback_log: Callable[[str], None] | None = None,
        generar_auditoria_md: bool = True,
    ) -> tuple[FichaNegocioLens, Path | None]:
        """Procesa una URL individual mediante el subservicio dedicado, guardando CSV y cerrando sesion."""
        self._cancelado = False
        resultado = await self._procesador_url.ejecutar(
            fuente_imagen=fuente_imagen,
            id_registro=id_registro,
            carpeta_salida=carpeta_salida,
            cerrar_navegador_al_terminar=cerrar_navegador_al_terminar,
            callback_log=callback_log,
            generar_auditoria_md=generar_auditoria_md,
        )
        self.ultima_salida = resultado[1]
        return resultado

    async def procesar_csv_con_lens(
        self,
        ruta_csv: Path,
        columna_imagen: str,
        nombre_hoja: str | None = None,
        callback_progreso: Callable[[int, int, str], None] | None = None,
        callback_log: Callable[[str], None] | None = None,
        carpeta_salida: Path | None = None,
        generar_auditoria_md: bool = True,
    ) -> tuple[list[FichaNegocioLens], Path]:
        """Procesa un archivo tabular (CSV o Excel) mediante el subservicio especializado."""
        self._cancelado = False
        resultado = await self._procesador_archivo.ejecutar(
            ruta_archivo=ruta_csv,
            columna_imagen=columna_imagen,
            nombre_hoja=nombre_hoja,
            carpeta_salida=carpeta_salida,
            callback_progreso=callback_progreso,
            callback_log=callback_log,
            verificador_cancelacion=lambda: self._cancelado,
            generar_auditoria_md=generar_auditoria_md,
        )
        self.ultima_salida = resultado[1]
        return resultado

    async def procesar_carpeta_imagenes_lens(
        self,
        carpeta: Path,
        callback_progreso: Callable[[int, int, str], None] | None = None,
        callback_log: Callable[[str], None] | None = None,
        archivos_especificos: list[Path] | None = None,
        modo_escritura: str = "sobrescribir",
        csv_existente: Path | None = None,
        carpeta_salida: Path | None = None,
        generar_auditoria_md: bool = True,
    ) -> tuple[list[FichaNegocioLens], Path]:
        """Procesa una coleccion de imagenes mediante el subservicio incremental especializado."""
        self._cancelado = False
        resultado = await self._procesador_carpeta.ejecutar(
            carpeta=carpeta,
            callback_progreso=callback_progreso,
            callback_log=callback_log,
            archivos_especificos=archivos_especificos,
            modo_escritura=modo_escritura,
            csv_existente=csv_existente,
            carpeta_salida=carpeta_salida,
            verificador_cancelacion=lambda: self._cancelado,
            generar_auditoria_md=generar_auditoria_md,
        )
        self.ultima_salida = resultado[1]
        return resultado

    async def procesar_modo_ia_lote(
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
    ) -> tuple[list[dict[str, Any]], Path | None]:
        """Procesa registros en Modo IA mediante el subservicio conversacional especializado."""
        self._cancelado = False
        resultado = await self._procesador_modo_ia.ejecutar(
            filas=filas,
            instrucciones=instrucciones,
            columnas=columnas,
            tamano_lote=tamano_lote,
            lotes_por_conversacion=lotes_por_conversacion,
            callback_progreso=callback_progreso,
            callback_log=callback_log,
            nombre_salida=nombre_salida,
            carpeta_salida=carpeta_salida,
            verificador_cancelacion=lambda: self._cancelado,
        )
        self.ultima_salida = resultado[1]
        return resultado
