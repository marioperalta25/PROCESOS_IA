"""Fabrica para instanciar el lector de flujos adecuado según el archivo."""

from __future__ import annotations

from pathlib import Path

from procesos_ia.aplicacion.contratos import LectorFlujoProtocol
from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.infraestructura.archivos.lector_csv import LectorCsv
from procesos_ia.infraestructura.archivos.lector_xlsx import LectorXlsx


def crear_lector_flujo(
    ruta_archivo: Path,
    codificacion_forzada: str | None = None,
    delimitador_forzado: str | None = None,
    nombre_hoja_excel: str | None = None,
) -> LectorFlujoProtocol:
    """Devuelve el lector correspondiente segun la extension del archivo."""
    sufijo = ruta_archivo.suffix.lower()

    if sufijo in {".csv", ".txt", ".tsv", ".tab"}:
        return LectorCsv(
            codificacion_forzada=codificacion_forzada,
            delimitador_forzado=delimitador_forzado,
        )

    if sufijo in {".xlsx", ".xlsm"}:
        return LectorXlsx(nombre_hoja=nombre_hoja_excel)

    formatos_soportados = ".csv, .txt, .tsv, .xlsx, .xlsm"
    raise ErrorProcesamiento(
        f"Formato de archivo no soportado '{sufijo}'. Formatos admitidos: {formatos_soportados}"
    )
