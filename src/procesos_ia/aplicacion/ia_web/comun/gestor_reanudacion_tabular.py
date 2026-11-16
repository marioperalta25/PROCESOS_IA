"""Especializacion para deteccion y reanudacion de datos tabulares (CSVs).

Consumido por Modo IA (IA General), DeepSeek Web, Gemini Web y Google Lens CSV.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from procesos_ia.aplicacion.comun.gestor_reanudacion_base import (
    COLUMNA_ESTADO,
    COLUMNA_FECHA,
    COLUMNA_ID,
    COLUMNA_MOTIVO,
    GestorReanudacionBase,
    identificar_fila,
)
from procesos_ia.aplicacion.comun.identidad_tabular import IdentidadTabular, buscar_identidad, parametros_tabulares
from procesos_ia.aplicacion.comun.trabajo_tabular import TrabajoTabular, leer_progreso
from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.dominio.reanudacion import (
    AccionReanudacion,
    EstadoIA,
    RegistroEstado,
    ResumenReanudacion,
)


class GestorReanudacionTabular(GestorReanudacionBase):
    """Subclase especializada en el flujo de CSVs por lotes o conversacional."""

    def __init__(self, enrutador: EnrutadorSalidas, raiz_destino: Path | None = None) -> None:
        self._enrutador = enrutador
        self._raiz_destino = raiz_destino

    def preparar_trabajo(
        self, ruta_origen: Path, modulo: str, instrucciones: str,
        columnas: list[str] | None, filas: list[dict[str, Any]], opciones: dict | None = None,
    ) -> TrabajoTabular:
        """Resuelve la copia compatible a partir del original sin escribir ni mover archivos."""
        parametros = parametros_tabulares()
        identidad = IdentidadTabular.crear(ruta_origen, modulo, filas, instrucciones, columnas, opciones)
        gestor = self._enrutador.gestor_procesos(self._raiz_destino)
        respaldo = buscar_identidad(gestor, identidad, parametros)
        anteriores = None
        if respaldo:
            anteriores = leer_progreso(respaldo, parametros)
            if len(anteriores) != len(filas):
                raise ValueError(parametros["error_filas"])
        elif modulo == "modo_ia":
            from procesos_ia.aplicacion.comun.respaldo_tabular_anterior import importar_respaldo_anterior
            for candidata in self._candidatas(modulo, ruta_origen):
                if (candidata.parent / parametros["archivo_identidad"]).exists():
                    continue
                recuperadas = importar_respaldo_anterior(candidata, filas, instrucciones, columnas, parametros)
                if recuperadas:
                    respaldo, anteriores = candidata, recuperadas
                    break
        return TrabajoTabular(filas, identidad, respaldo, anteriores)

    def buscar_respaldo_existente(self, modulo: str, ruta_archivo: Path) -> Path | None:
        """Localiza si existe una corrida previa asociada a este CSV en estados inconclusos."""
        candidatas = self._candidatas(modulo, ruta_archivo)
        return candidatas[0] if candidatas else None

    def _candidatas(self, modulo: str, ruta_archivo: Path) -> list[Path]:
        nombre_base = ruta_archivo.stem.lower()
        gestor = self._enrutador.gestor_procesos(self._raiz_destino)
        base_modulo = gestor.rama(modulo)
        if not base_modulo.is_dir():
            return []

        candidatas: list[Path] = []
        for estado in ("cancelados", "en_proceso", "fallidos"):
            carpeta_estado = base_modulo / gestor.configuracion["estados"].get(estado, estado)
            if carpeta_estado.is_dir():
                candidatas.extend(
                    list(carpeta_estado.glob(f"*{nombre_base}*.csv"))
                    + list(carpeta_estado.glob(f"*/*{nombre_base}*.csv"))
                )

        candidatas.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidatas

    def evaluar_origen(
        self, ruta_origen: Path, modulo: str = "modo_ia",
    ) -> tuple[list[RegistroEstado], ResumenReanudacion]:
        """Evalua si el archivo directo o un respaldo previo amerita reanudacion."""
        regs_directos, resumen = self.inspeccionar_csv(ruta_origen)
        if resumen.requiere_decision:
            return regs_directos, resumen

        respaldo = self.buscar_respaldo_existente(modulo, ruta_origen)
        if respaldo and respaldo.is_file():
            regs_respaldo, resumen_respaldo = self.inspeccionar_csv(respaldo)
            if resumen_respaldo.requiere_decision:
                resumen_respaldo.ruta_respaldo = respaldo
                return regs_respaldo, resumen_respaldo

        return regs_directos, resumen

    @classmethod
    def preparar_filas_para_envio(
        cls,
        filas_originales: list[dict[str, Any]],
        registros_evaluados: list[RegistroEstado],
        accion: AccionReanudacion,
    ) -> list[dict[str, Any]]:
        """Prepara la coleccion de filas enriquecidas con metadatos segun la accion."""
        if accion == AccionReanudacion.REINICIAR_TODO or not registros_evaluados:
            resultado = []
            for idx, f in enumerate(filas_originales, start=1):
                f_nueva = dict(f)
                f_nueva[COLUMNA_ID] = identificar_fila(f, idx)
                f_nueva[COLUMNA_ESTADO] = EstadoIA.PENDIENTE.value
                f_nueva[COLUMNA_MOTIVO] = ""
                f_nueva[COLUMNA_FECHA] = ""
                resultado.append(f_nueva)
            return resultado

        mapa_evaluados = {r.id_registro: r for r in registros_evaluados}
        filas_procesar: list[dict[str, Any]] = []

        for idx, f in enumerate(filas_originales, start=1):
            id_reg = identificar_fila(f, idx)
            reg_prev = mapa_evaluados.get(id_reg)
            if not reg_prev:
                f_copia = dict(f)
                f_copia[COLUMNA_ID] = id_reg
                f_copia[COLUMNA_ESTADO] = EstadoIA.PENDIENTE.value
                filas_procesar.append(f_copia)
                continue

            if accion == AccionReanudacion.REPROCESAR_PENDIENTES_Y_FALLIDOS:
                if reg_prev.es_reintentable:
                    f_copia = dict(f)
                    f_copia[COLUMNA_ID] = id_reg
                    f_copia[COLUMNA_ESTADO] = EstadoIA.PENDIENTE.value
                    f_copia[COLUMNA_MOTIVO] = f"Reintento desde estado previo: {reg_prev.estado.value}"
                    filas_procesar.append(f_copia)
            elif accion == AccionReanudacion.SOLO_PENDIENTES:
                if reg_prev.estado == EstadoIA.PENDIENTE:
                    f_copia = dict(f)
                    f_copia[COLUMNA_ID] = id_reg
                    filas_procesar.append(f_copia)

        return filas_procesar
