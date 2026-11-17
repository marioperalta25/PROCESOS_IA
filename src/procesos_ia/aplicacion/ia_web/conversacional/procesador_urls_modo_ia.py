"""Modulo de aplicacion para procesar CSV/Excel de URLs por lotes en Modo IA."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from procesos_ia.aplicacion.comun.trabajo_tabular import TrabajoTabular
from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.conversacional.constructor_prompt_imagenes import CAMPOS_DISPONIBLES
from procesos_ia.aplicacion.ia_web.conversacional.procesador_modo_ia import ProcesadorModoIA
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver


def construir_instrucciones_urls_modo_ia(
    campos_activos: list[str] | tuple[str, ...] | dict[str, bool],
    instrucciones_adicionales: str = "",
) -> str:
    """Genera instrucciones estructuradas para analizar lotes de URLs en Modo IA."""
    if isinstance(campos_activos, dict):
        claves = [k for k, v in campos_activos.items() if v and k in CAMPOS_DISPONIBLES]
    else:
        claves = [k for k in campos_activos if k in CAMPOS_DISPONIBLES]
    if not claves:
        claves = ["negocio", "telefonos"]

    reglas_campos = "\n".join(f"- {c}: {CAMPOS_DISPONIBLES[c]['descripcion']}" for c in claves)
    ejemplo = ", ".join(f'"{c}": "{CAMPOS_DISPONIBLES[c]["ejemplo"]}"' for c in claves)
    extra = f"\nINSTRUCCIONES ADICIONALES:\n{instrucciones_adicionales.strip()}\n" if instrucciones_adicionales.strip() else ""
    return (
        "Eres un extractor de datos comerciales. Para cada fila recibida, inspecciona la URL de imagen o ficha "
        "y extrae unicamente la informacion solicitada.\n\n"
        f"CAMPOS REQUERIDOS:\n{reglas_campos}\n"
        f"{extra}\n"
        "FORMATO DE RESPUESTA OBLIGATORIO:\n"
        "1. Responde EXCLUSIVAMENTE un bloque JSON valido con la clave \"resultados\" y un objeto por cada fila, "
        "usando en \"id\" el numero exacto de [FILA N] (ejemplo: 1, 2, 3):\n"
        f'{{"resultados": [{{"id": 1, {ejemplo}}}]}}\n'
        "2. Si un dato no existe o no es legible, asigna \"ND\".\n"
        "3. Si hay multiples telefonos en una fila, separalos con \" / \".\n"
        "4. No incluyas texto introductorio, explicaciones ni saludos fuera del JSON."
    ).strip()


class ProcesadorUrlsModoIA:
    """Reutiliza ProcesadorModoIA para evaluar columnas de URLs por lotes configurables."""

    def __init__(
        self,
        gestor_sesion: GestorSesionNodriver,
        enrutador: EnrutadorSalidas,
        configuracion: ConfiguracionWeb,
    ) -> None:
        self._procesador_lote = ProcesadorModoIA(gestor_sesion, enrutador, configuracion)

    async def ejecutar(
        self,
        filas: list[dict[str, Any]],
        columna_url: str,
        campos_activos: list[str] | dict[str, bool],
        instrucciones_adicionales: str = "",
        tamano_lote: int = 3,
        lotes_por_conversacion: int = 4,
        nombre_salida: str = "urls_modo_ia",
        carpeta_salida: Path | None = None,
        callback_progreso: Callable[[int, int, str], None] | None = None,
        callback_log: Callable[[str], None] | None = None,
        verificador_cancelacion: Callable[[], bool] | None = None,
        generar_auditoria_md: bool = True,
        trabajo_tabular: TrabajoTabular | None = None,
    ) -> tuple[list[dict[str, Any]], Path | None]:
        """Ejecuta el lote de URLs en Modo IA heredando resiliencia, CSV y auditoria MD."""
        instrucciones = construir_instrucciones_urls_modo_ia(campos_activos, instrucciones_adicionales)
        return await self._procesador_lote.ejecutar(
            filas=filas,
            instrucciones=instrucciones,
            columnas=[columna_url],
            tamano_lote=tamano_lote,
            lotes_por_conversacion=lotes_por_conversacion,
            callback_progreso=callback_progreso,
            callback_log=callback_log,
            nombre_salida=nombre_salida,
            carpeta_salida=carpeta_salida,
            verificador_cancelacion=verificador_cancelacion,
            generar_auditoria_md=generar_auditoria_md,
            trabajo_tabular=trabajo_tabular,
        )
