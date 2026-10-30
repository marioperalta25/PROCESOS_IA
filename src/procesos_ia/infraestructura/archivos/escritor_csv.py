"""Escritura tabular atomica; el consumidor decide ruta, columnas y transformaciones."""

import csv
import os
from pathlib import Path
import tempfile
from typing import Any


def guardar_filas_csv(filas: list[dict[str, Any]], destino: Path) -> Path:
    """Reemplaza una salida de trabajo propia conservando todos sus campos."""
    campos = list(dict.fromkeys(clave for fila in filas for clave in fila))
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8-sig", newline="", dir=destino.parent,
            prefix=destino.stem, suffix=".tmp", delete=False,
        ) as archivo:
            temporal = Path(archivo.name)
            escritor = csv.DictWriter(archivo, fieldnames=campos)
            escritor.writeheader()
            escritor.writerows(filas)
            archivo.flush()
            os.fsync(archivo.fileno())
        temporal.replace(destino)
    finally:
        if temporal is not None:
            temporal.unlink(missing_ok=True)
    return destino
