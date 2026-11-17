"""Servicio de procesamiento masivo tabular e imagenes para DeepSeek y Gemini Web."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.comun.identidad_tabular import IdentidadTabular
from procesos_ia.aplicacion.comun.trabajo_tabular import TrabajoTabular
from procesos_ia.aplicacion.ia_web.visual_1a1.procesador_archivo_urls import leer_filas_archivo_tabular
from procesos_ia.aplicacion.ia_web.conversacional.mapeo_respuestas_tabulares import mapear_respuestas_lote
from procesos_ia.aplicacion.ia_web.comun.diagnostico_lotes import (
    evaluar_calidad_lote, notificar_balance_lote, notificar_cierre_exitoso,
    notificar_envio_lote, notificar_fallo_envio_lote, notificar_respuesta_lote,
)
from procesos_ia.aplicacion.ia_web.comun.guardador_extracciones import guardar_auditoria_modo_ia_md
from procesos_ia.aplicacion.ia_web.conversacional.formateador_lotes_chat import construir_prompt_lote_chat
from procesos_ia.aplicacion.comun.gestor_reanudacion_base import (
    COLUMNA_ESTADO, COLUMNA_FECHA, COLUMNA_MOTIVO, GestorReanudacionBase,
)
from procesos_ia.dominio.reanudacion import EstadoIA
from procesos_ia.dominio.excepciones import ErrorPersistenciaTabular
from procesos_ia.dominio.normalizador import formatear_columnas_delimitadas, normalizar_texto
from procesos_ia.infraestructura.archivos.escritor_csv import guardar_filas_csv
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.extractor_json import extraer_y_reparar_json
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.infraestructura.web.motores.manipulador_dom_deepseek import (
    enviar_prompt_deepseek, esperar_respuesta_deepseek, iniciar_nuevo_chat_deepseek,
)
from procesos_ia.infraestructura.web.motores.manipulador_dom_gemini import (
    enviar_prompt_gemini, esperar_respuesta_gemini, iniciar_nuevo_chat_gemini,
)

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

    @property
    def gestor_sesion(self) -> GestorSesionNodriver:
        return self._gestor

    def configurar(self, configuracion: ConfiguracionWeb) -> None:
        self._gestor.actualizar_configuracion(configuracion)
        self._config = configuracion

    def cancelar(self) -> None:
        self._cancelado = True

    async def cerrar_navegador(self) -> None:
        """Cierra el navegador y libera recursos."""
        await self._gestor.cerrar()

    def forzar_cierre_inmediato(self) -> None:
        """Termina el árbol de procesos de Chromium y remueve bloqueos del perfil."""
        self._cancelado = True
        self._gestor.forzar_cierre_inmediato()
        self._config.limpiar_bloqueos_perfil()

    async def _obtener_pestana(self, motor: str, callback_log: Callable[[str], None] | None = None) -> Any:
        url = self._config.url_gemini if motor == "gemini" else self._config.url_deepseek
        patrones = ("Gemini", "Google") if motor == "gemini" else ("DeepSeek",)
        pestana = await self._gestor.navegar_o_reutilizar(url, patrones)
        aviso_v = getattr(self._gestor, "ultimo_aviso_ventana", None)
        if aviso_v and callback_log: callback_log(f"[ALERTA] {aviso_v}")
        return pestana

    async def _rotar_chat_si_requerido(self, pestana: Any, motor: str, limite: int) -> None:
        if limite > 0 and self._consultas_chat >= limite:
            await (iniciar_nuevo_chat_gemini(pestana) if motor == "gemini" else iniciar_nuevo_chat_deepseek(pestana))
            self._consultas_chat = 0; await asyncio.sleep(1.5)

    def _resolver_imagen(self, fila: dict[str, Any], col_img: str | None, carpeta_img: Path | None) -> Path | None:
        if not col_img and not carpeta_img: return None
        val = str(fila.get(col_img, "")).strip() if col_img else ""
        if val:
            p = Path(val)
            if p.is_file(): return p
            if carpeta_img and carpeta_img.is_dir():
                c = carpeta_img / val
                if c.is_file(): return c
                for ext in (".jpg", ".jpeg", ".png", ".webp"):
                    ce = carpeta_img / f"{val}{ext}"
                    if ce.is_file(): return ce
        return None

    async def procesar_csv(
        self, motor: str, ruta_csv: Path, columnas: list[str], instrucciones: str,
        tamano_lote: int = 5, columna_imagen: str | None = None, carpeta_imagenes: Path | None = None,
        rotacion_chat: int = 2, callback_progreso: Callable | None = None, callback_log: Callable | None = None,
        generar_auditoria_md: bool = True, salida_existente: Any | None = None,
        trabajo_tabular: TrabajoTabular | None = None, nombre_hoja: str | None = None,
    ) -> tuple[list[dict[str, Any]], Path]:
        """Procesa registros del CSV enviando lotes de texto o imagenes 1 a 1 al navegador."""
        self._cancelado = False
        self._consultas_chat = 0
        motor = motor.lower().strip()

        filas = trabajo_tabular.filas_pendientes if trabajo_tabular else leer_filas_archivo_tabular(ruta_csv, nombre_hoja)
        trabajo = trabajo_tabular or TrabajoTabular(
            filas, IdentidadTabular.crear(ruta_csv, motor, filas, instrucciones, columnas, {"hoja": nombre_hoja}),
        )
        filas = trabajo.filas_pendientes

        total_filas = len(filas)
        if trabajo.solo_exportar:
            with trabajo.abrir(self._enrutador, f"{motor}_evaluacion_{ruta_csv.stem}.csv", salida_existente=salida_existente):
                return [], trabajo.finalizar("completados")
        if total_filas == 0:
            raise ValueError("El archivo CSV no contiene registros para procesar.")

        pestana = await self._obtener_pestana(motor, callback_log)
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
            generar_auditoria_md=generar_auditoria_md,
            salida_existente=salida_existente, trabajo_tabular=trabajo,
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
        pestana = await self._obtener_pestana(motor, callback_log)
        return await self._procesar_flujo_imagenes(
            motor, pestana, filas, ["archivo"], instrucciones, "ruta_archivo",
            carpeta, rotacion_chat, f"carpeta_{carpeta.name}", callback_progreso, callback_log,
        )

    async def procesar_imagen_individual(
        self, motor: str, ruta_img: Path, instrucciones: str,
        callback_progreso: Callable | None = None, callback_log: Callable | None = None,
    ) -> tuple[list[dict[str, Any]], Path]:
        self._cancelado = False; self._consultas_chat = 0
        if not ruta_img.is_file(): raise ValueError(f"Archivo no existe: {ruta_img}")
        filas = [{"id": 1, "archivo": ruta_img.name, "ruta_archivo": str(ruta_img)}]
        pestana = await self._obtener_pestana(motor, callback_log)
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
        with self._enrutador.reservar_salida(motor, f"{motor}_imagenes_{stem}.csv") as salida:
            total, resultados = len(filas), []
            if cb_log:
                cb_log(f"[INFO] Modo visual en {motor.upper()}: {total} imágenes (1 a 1)")
            try:
                for idx, fila in enumerate(filas, start=1):
                    if self._cancelado: break
                    await self._rotar_chat_si_requerido(pestana, motor, rotacion)
                    if self._cancelado: break
                    ruta_img = self._resolver_imagen(fila, col_img, carpeta_img)
                    prompt = (
                        f"{instrucciones}\n\nDATOS DE LA IMAGEN O REGISTRO (delimitados por '|'):\n"
                        f"[FILA {idx}]: {formatear_columnas_delimitadas(fila, columnas)}\n\n"
                        f"Analiza la imagen adjunta y responde en JSON: {{\"calificacion\": \"...\", \"motivo\": \"...\"}}"
                    )
                    if cb_log:
                        cb_log(f"[INFO] Fila {idx}/{total}: Enviando a {motor.upper()}...")
                    enviado = (await enviar_prompt_gemini(pestana, prompt, ruta_img)) if motor == "gemini" else (await enviar_prompt_deepseek(pestana, prompt, ruta_img))
                    self._consultas_chat += 1
                    if self._cancelado: break
                    if not enviado:
                        f_sal = dict(fila); f_sal["error_inferencia"] = "Fallo de envio"; resultados.append(f_sal)
                        if cb_prog: cb_prog(idx, total, f"Imagen {idx}/{total} (fallo de envío)"); continue
                    resp_txt = (await esperar_respuesta_gemini(pestana, self._config.tiempo_espera_respuesta_segundos, verificador_cancelacion=lambda: self._cancelado)) if motor == "gemini" else (await esperar_respuesta_deepseek(pestana, self._config.tiempo_espera_respuesta_segundos, verificador_cancelacion=lambda: self._cancelado))
                    if self._cancelado: break
                    parsed = extraer_y_reparar_json(resp_txt)
                    f_sal = dict(fila)
                    if isinstance(parsed, dict): f_sal.update(parsed)
                    else: f_sal["respuesta_modelo"] = normalizar_texto((resp_txt or "")[:400])
                    resultados.append(f_sal); guardar_filas_csv(resultados, salida.ruta)
                    if cb_log: cb_log(f"[OK] Fila {idx} completada.")
                    if cb_prog: cb_prog(idx, total, f"Imagen {idx}/{total} completada")
                    await asyncio.sleep(0.5)
            except Exception as err:
                if not self._cancelado: raise
                if cb_log: cb_log(f"[INFO] Procesamiento cancelado: {err}")
            guardar_filas_csv(resultados, salida.ruta)
            estado = "cancelados" if self._cancelado else "completados"
            if estado == "completados" and any("error_inferencia" in f or "respuesta_modelo" in f for f in resultados):
                estado = "fallidos"
            return resultados, salida.finalizar(estado)

    async def _procesar_flujo_texto_lotes(
        self, motor: str, pestana: Any, filas: list[dict[str, Any]],
        columnas: list[str], instrucciones: str, tamano_lote: int,
        rotacion: int, stem: str,
        cb_prog: Callable | None, cb_log: Callable | None,
        generar_auditoria_md: bool = True,
        salida_existente: Any | None = None,
        trabajo_tabular: TrabajoTabular | None = None,
    ) -> tuple[list[dict[str, Any]], Path]:
        trabajo = trabajo_tabular or TrabajoTabular(
            filas, IdentidadTabular.crear(None, motor, filas, instrucciones, columnas),
        )
        filas = trabajo.filas_pendientes
        with trabajo.abrir(self._enrutador, f"{motor}_evaluacion_{stem}.csv", salida_existente=salida_existente) as salida:
            if trabajo.respaldo:
                trabajo.notificar_progreso(cb_prog, 0, trabajo.parametros["progreso_recuperado"])
            total = len(filas); total_lotes = (total + tamano_lote - 1) // tamano_lote
            resultados: list[dict[str, Any]] = []
            ruta_md = salida.ruta.with_suffix(".md") if generar_auditoria_md else None
            if ruta_md and not ruta_md.exists():
                guardar_auditoria_modo_ia_md(ruta_md, 0, total_lotes, 0, 0, "", "", prompt_inicial=instrucciones)
            if cb_log:
                cb_log(f"[INFO] Modo texto en {motor.upper()}: {total} filas en {total_lotes} lote(s) de {tamano_lote}")
            fecha_iso = GestorReanudacionBase.fecha_actual_iso()
            try:
                for n_lote, i in enumerate(range(0, total, tamano_lote), start=1):
                    if self._cancelado: break
                    lote = filas[i : i + tamano_lote]
                    lote_resultado: list[dict[str, Any]] = []
                    evaluadas = 0
                    for intento_lote in range(3):
                        if self._cancelado: break
                        await self._rotar_chat_si_requerido(pestana, motor, rotacion)
                        if self._cancelado: break
                        prompt = construir_prompt_lote_chat(instrucciones=instrucciones, lote_filas=lote, columnas_seleccionadas=columnas, indice_inicio=i + 1)
                        notificar_envio_lote(cb_log, n_lote, total_lotes, i + 1, min(i + tamano_lote, total), total, delimitador="|")
                        t_ini = asyncio.get_running_loop().time()
                        enviado = (await enviar_prompt_gemini(pestana, prompt, None)) if motor == "gemini" else (await enviar_prompt_deepseek(pestana, prompt, None))
                        self._consultas_chat += 1
                        if self._cancelado: break
                        if not enviado:
                            notificar_fallo_envio_lote(cb_log, n_lote)
                            lote_resultado = [{**dict(f), "error_inferencia": "Fallo de envio", COLUMNA_ESTADO: EstadoIA.FALLIDO.value, COLUMNA_MOTIVO: "[ERROR] Fallo de envio al motor", COLUMNA_FECHA: fecha_iso} for f in lote]
                            break
                        resp_txt = (await esperar_respuesta_gemini(pestana, self._config.tiempo_espera_respuesta_segundos, verificador_cancelacion=lambda: self._cancelado)) if motor == "gemini" else (await esperar_respuesta_deepseek(pestana, self._config.tiempo_espera_respuesta_segundos, verificador_cancelacion=lambda: self._cancelado))
                        if self._cancelado: break
                        t_dur = asyncio.get_running_loop().time() - t_ini
                        notificar_respuesta_lote(cb_log, n_lote, total_lotes, t_dur)
                        if ruta_md:
                            guardar_auditoria_modo_ia_md(ruta_md, n_lote, total_lotes, i + 1, min(i + tamano_lote, total), prompt, resp_txt or "", t_dur)
                        parsed = extraer_y_reparar_json(resp_txt)
                        lote_resultado = mapear_respuestas_lote(resp_txt or "", parsed, lote, i + 1)
                        if not resp_txt:
                            for fila in lote_resultado: fila[COLUMNA_ESTADO] = EstadoIA.FALLIDO.value
                        evaluadas, _ = evaluar_calidad_lote(lote_resultado, len(lote))
                        if (not resp_txt or evaluadas < len(lote)) and intento_lote < 2 and not self._cancelado:
                            if cb_log: cb_log(f"[ALERTA] Lote {n_lote} incompleto ({evaluadas}/{len(lote)}). Rotando chat y reintentando ({intento_lote + 1}/2)...")
                            self._consultas_chat = rotacion; await asyncio.sleep(0.5); continue
                        break
                    if self._cancelado: break
                    notificar_balance_lote(cb_log, n_lote, evaluadas, len(lote))
                    trabajo.confirmar(lote_resultado); resultados.extend(lote_resultado)
                    trabajo.notificar_progreso(cb_prog, min(i + len(lote), total), f"Lote {n_lote}/{total_lotes} completado")
                    await asyncio.sleep(0.5)
            except (ErrorPersistenciaTabular, ValueError):
                raise
            except (Exception, asyncio.CancelledError) as err:
                if not self._cancelado: raise
                if cb_log: cb_log(f"[INFO] Procesamiento cancelado: {err}")
            estado = "cancelados" if self._cancelado else "completados"
            ruta_final = trabajo.finalizar(estado)
            if salida.estado == "completados":
                notificar_cierre_exitoso(cb_log, ruta_final, ruta_final.with_suffix(".md") if ruta_md else None)
            return resultados, ruta_final
