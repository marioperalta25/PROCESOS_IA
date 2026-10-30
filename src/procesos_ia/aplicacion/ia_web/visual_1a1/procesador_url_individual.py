"""Modulo de aplicacion para procesamiento de imagen o URL individual en Google Lens."""

from __future__ import annotations

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

        with self._enrutador.reservar_salida(
            "imagenes", f"extraccion_url_{id_registro}.csv", raiz_destino=carpeta_salida,
        ) as salida:
            try:
                ficha = await self._ejecutor_lens(
                    fuente_imagen=fuente_imagen, id_registro=id_registro,
                    cerrar_pestana=True, callback_log=callback_log,
                )
                guardar_ficha_individual_csv(
                    ficha, salida.directorio, salida.nombre_archivo,
                    generar_auditoria_md=generar_auditoria_md,
                )
            finally:
                if cerrar_navegador_al_terminar:
                    if callback_log:
                        callback_log("[INFO] Cerrando navegador tras completar la URL individual...")
                    await self._gestor.cerrar_navegador()
            estado = "cancelados" if ficha.estado_ia == "CANCELADO" else "completados"
            if ficha.estado_ia.startswith("ERROR") or ficha.estado_ia.startswith("TIMEOUT"):
                estado = "fallidos"
            ruta_csv = salida.finalizar(estado)
            if callback_log:
                callback_log(f"[OK] Guardado en CSV: {ruta_csv.resolve()}")
            return ficha, ruta_csv
