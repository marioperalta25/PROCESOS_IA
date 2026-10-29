"""Modulo de aplicacion para procesamiento de imagen o URL individual en Google Lens."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.comun.guardador_extracciones import guardar_ficha_individual_csv
from procesos_ia.dominio.ia_web.ficha_negocio import FichaNegocioLens
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver


class ProcesadorUrlIndividual:
    """Ejecuta el analisis de una sola URL o imagen, persiste en CSV y cierra el navegador."""

    def __init__(
        self,
        gestor_sesion: GestorSesionNodriver,
        enrutador: EnrutadorSalidas,
        configuracion: ConfiguracionWeb,
        ejecutor_lens: Callable[..., Any],
    ) -> None:
        self._gestor = gestor_sesion
        self._enrutador = enrutador
        self._config = configuracion
        self._ejecutor_lens = ejecutor_lens

    async def ejecutar(
        self,
        fuente_imagen: str,
        id_registro: str = "img_1",
        carpeta_salida: Path | None = None,
        cerrar_navegador_al_terminar: bool = True,
        callback_log: Callable[[str], None] | None = None,
        generar_auditoria_md: bool = True,
    ) -> tuple[FichaNegocioLens, Path | None]:
        """Procesa una URL individual, almacena en CSV y asegura el cierre del navegador."""
        if callback_log:
            callback_log(f"[INFO] Iniciando procesamiento individual de: {fuente_imagen}")

        # Ejecuta la extraccion de Lens asegurando cerrar la pestana activa al finalizar
        ficha: FichaNegocioLens = await self._ejecutor_lens(
            fuente_imagen=fuente_imagen,
            id_registro=id_registro,
            cerrar_pestana=True,
            callback_log=callback_log,
        )

        ruta_csv: Path | None = None
        destino = carpeta_salida if carpeta_salida is not None else self._enrutador.extracciones

        try:
            ruta_csv = guardar_ficha_individual_csv(
                ficha, destino, generar_auditoria_md=generar_auditoria_md
            )
            if callback_log:
                callback_log(f"[OK] Guardado en CSV: {ruta_csv.resolve()}")
        except Exception as error:
            if callback_log:
                callback_log(f"[ERROR] No se pudo guardar en CSV: {error}")

        if cerrar_navegador_al_terminar:
            if callback_log:
                callback_log("[INFO] Cerrando navegador tras completar la URL individual...")
            try:
                await self._gestor.cerrar_navegador()
                if callback_log:
                    callback_log("[OK] Navegador cerrado exitosamente.")
            except Exception as error:
                if callback_log:
                    callback_log(f"[ALERTA] Detalle al cerrar navegador: {error}")

        return ficha, ruta_csv
