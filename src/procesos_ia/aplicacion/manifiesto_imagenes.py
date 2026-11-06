"""Manifiesto persistente y rotativo para registro de imagenes procesadas.

Mantiene un indice liviano en texto plano delimitado, con limite estricto de 4 MB
y rotacion FIFO para soportar decenas de miles de registros sin degradar la memoria.
"""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path

LIMITE_BYTES_MANIFIESTO = 4 * 1024 * 1024  # 4 MB maximo


class ManifiestoImagenes:
    """Gestiona el historial persistente de imagenes procesadas por carpeta."""

    def __init__(
        self, ruta_archivo: Path, max_bytes: int = LIMITE_BYTES_MANIFIESTO
    ) -> None:
        self._ruta = Path(ruta_archivo)
        self._max_bytes = max_bytes

    @property
    def ruta(self) -> Path:
        """Ruta física del archivo de manifiesto en disco."""
        return self._ruta

    def registrar(self, nombre_carpeta: str, nombre_archivo: str) -> None:
        """Registra una imagen procesada en modo append O(1)."""
        if not nombre_carpeta or not nombre_archivo:
            return

        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().isoformat(timespec="seconds")
        carp = nombre_carpeta.strip().lower()
        arch = nombre_archivo.strip()
        linea = f"{ts}|{carp}|{arch}\n"

        with open(self._ruta, mode="a", encoding="utf-8", errors="ignore") as f:
            f.write(linea)

        self._verificar_y_rotar()

    def obtener_procesadas(self, nombre_carpeta: str) -> set[str]:
        """Obtiene el conjunto de nombres de archivos ya procesados para una carpeta."""
        if not self._ruta.is_file() or not nombre_carpeta:
            return set()

        carp_buscada = nombre_carpeta.strip().lower()
        procesadas: set[str] = set()

        try:
            with open(self._ruta, mode="r", encoding="utf-8", errors="ignore") as f:
                for linea in f:
                    partes = linea.rstrip("\r\n").split("|")
                    if len(partes) >= 3:
                        carp_reg = partes[1].strip().lower()
                        arch_reg = partes[2].strip()
                        if carp_reg == carp_buscada and arch_reg:
                            procesadas.add(arch_reg.lower())
        except Exception:
            pass

        return procesadas

    def limpiar_carpeta(self, nombre_carpeta: str) -> None:
        """Elimina del manifiesto las entradas correspondientes a una carpeta especifica."""
        if not self._ruta.is_file() or not nombre_carpeta:
            return

        carp_buscada = nombre_carpeta.strip().lower()
        lineas_conservadas: list[str] = []

        try:
            with open(self._ruta, mode="r", encoding="utf-8", errors="ignore") as f:
                for linea in f:
                    partes = linea.rstrip("\r\n").split("|")
                    if len(partes) >= 3:
                        if partes[1].strip().lower() == carp_buscada:
                            continue
                    lineas_conservadas.append(linea)

            ruta_tmp = self._ruta.with_suffix(".tmp")
            with open(ruta_tmp, mode="w", encoding="utf-8") as f_tmp:
                f_tmp.writelines(lineas_conservadas)
            os.replace(ruta_tmp, self._ruta)
        except Exception:
            pass

    def _verificar_y_rotar(self, porcentaje_conservar: float = 0.5) -> None:
        """Poda el archivo si supera el limite maximo de bytes manteniendo las mas recientes."""
        try:
            if not self._ruta.is_file() or self._ruta.stat().st_size <= self._max_bytes:
                return

            with open(self._ruta, mode="r", encoding="utf-8", errors="ignore") as f:
                lineas = f.readlines()

            total_lineas = len(lineas)
            if total_lineas <= 1:
                return

            lineas_a_conservar = max(1, int(total_lineas * porcentaje_conservar))
            lineas_recientes = lineas[-lineas_a_conservar:]

            ruta_tmp = self._ruta.with_suffix(".tmp")
            with open(ruta_tmp, mode="w", encoding="utf-8") as f_tmp:
                f_tmp.writelines(lineas_recientes)
            os.replace(ruta_tmp, self._ruta)
        except Exception:
            pass

