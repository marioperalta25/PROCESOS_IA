"""Modulo base (Padre) para analisis y clasificacion de reanudacion granular.

Proporciona la logica troncal compartida tanto para datos tabulares como para
colecciones de imagenes en procesos Web (IA General, Gemini, DeepSeek, Lens) y Local.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from procesos_ia.dominio.reanudacion import (
    AccionReanudacion,
    EstadoIA,
    RegistroEstado,
    ResumenReanudacion,
)

COLUMNA_ESTADO = "_estado_ia"
COLUMNA_MOTIVO = "_motivo_estado"
COLUMNA_FECHA = "_fecha_procesamiento"
COLUMNA_ID = "_id_registro"


def identificar_fila(fila: dict[str, Any], indice: int, usar_id_externo: bool = True) -> str:
    """Conserva el identificador tabular o deriva uno estable de su posicion."""
    from procesos_ia.aplicacion.comun.identidad_tabular import parametros_tabulares
    prefijo = parametros_tabulares()["prefijo_fila"]
    externo = fila.get("id_registro") if usar_id_externo else None
    return str(fila.get(COLUMNA_ID) or externo or f"{prefijo}{indice}").strip()


class GestorReanudacionBase:
    """Clase base con utilidades de lectura linea a linea y clasificacion de estados."""

    @staticmethod
    def fecha_actual_iso() -> str:
        """Devuelve la marca temporal actual en formato ISO plano sin espacios."""
        return datetime.now().isoformat(timespec="seconds")

    @classmethod
    def extraer_metadatos_fila(cls, fila: dict[str, Any], indice_defecto: int) -> RegistroEstado:
        """Extrae el estado y motivo de una fila soportando variantes de nombres."""
        id_reg = str(
            fila.get(COLUMNA_ID)
            or fila.get("id_registro")
            or fila.get("fuente_imagen")
            or fila.get("archivo_imagen")
            or identificar_fila(fila, indice_defecto)
        ).strip()

        estado_crudo = (
            fila.get(COLUMNA_ESTADO)
            or fila.get("estado_ia")
            or ""
        )
        estado = EstadoIA.normalizar(str(estado_crudo)) if estado_crudo else EstadoIA.PENDIENTE

        motivo = str(fila.get(COLUMNA_MOTIVO) or fila.get("motivo") or "").strip()
        fecha = str(fila.get(COLUMNA_FECHA) or fila.get("fecha") or "").strip()

        return RegistroEstado(
            id_registro=id_reg,
            estado=estado,
            motivo=motivo,
            fecha_procesamiento=fecha,
            datos_originales=dict(fila),
        )

    @classmethod
    def clasificar_registros(cls, registros: list[RegistroEstado], origen: Path) -> ResumenReanudacion:
        """Calcula el balance estadistico de una lista de registros."""
        resumen = ResumenReanudacion(origen=origen, total=len(registros))
        tiene_meta = False

        for r in registros:
            if r.estado == EstadoIA.EXITOSO:
                resumen.exitosos += 1
                tiene_meta = True
            elif r.estado == EstadoIA.FALLIDO:
                resumen.fallidos += 1
                tiene_meta = True
            elif r.estado == EstadoIA.OMITIDO:
                resumen.omitidos += 1
                tiene_meta = True
            else:
                resumen.pendientes += 1

        resumen.tiene_metadatos = tiene_meta
        return resumen

    @classmethod
    def filtrar_por_accion(
        cls, registros: list[RegistroEstado], accion: AccionReanudacion
    ) -> list[RegistroEstado]:
        """Filtra la lista de registros segun la accion resuelta por el usuario."""
        if accion == AccionReanudacion.REPROCESAR_PENDIENTES_Y_FALLIDOS:
            return [r for r in registros if r.es_reintentable]
        if accion == AccionReanudacion.SOLO_PENDIENTES:
            return [r for r in registros if r.estado == EstadoIA.PENDIENTE]
        if accion == AccionReanudacion.REINICIAR_TODO:
            return [
                RegistroEstado(
                    id_registro=r.id_registro,
                    estado=EstadoIA.PENDIENTE,
                    motivo="",
                    fecha_procesamiento="",
                    datos_originales=r.datos_originales,
                )
                for r in registros
            ]
        return []

    @classmethod
    def inspeccionar_csv(cls, ruta_csv: Path) -> tuple[list[RegistroEstado], ResumenReanudacion]:
        """Lee un archivo CSV con lectura generadora linea a linea O(1) de memoria."""
        if not ruta_csv.is_file() or ruta_csv.stat().st_size == 0:
            res = ResumenReanudacion(origen=ruta_csv)
            return [], res

        registros: list[RegistroEstado] = []
        try:
            with open(ruta_csv, mode="r", encoding="utf-8-sig", errors="ignore") as f:
                lector = csv.DictReader(f)
                for idx, fila in enumerate(lector, start=1):
                    registros.append(cls.extraer_metadatos_fila(fila, idx))
        except Exception:
            return [], ResumenReanudacion(origen=ruta_csv)

        resumen = cls.clasificar_registros(registros, ruta_csv)
        return registros, resumen
