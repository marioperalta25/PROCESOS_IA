"""Adaptadores de infraestructura para manejo y lectura de archivos."""

from __future__ import annotations

from procesos_ia.infraestructura.archivos.fabrica_lectores import crear_lector_flujo
from procesos_ia.infraestructura.archivos.lector_csv import LectorCsv
from procesos_ia.infraestructura.archivos.lector_xlsx import LectorXlsx

__all__ = ["LectorCsv", "LectorXlsx", "crear_lector_flujo"]
