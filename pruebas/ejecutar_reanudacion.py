"""Comprobaciones de reanudacion y sus consumidores, sin servicios externos."""

import os
from pathlib import Path
import sys
import unittest


def main() -> int:
    """Prepara imports del proyecto y ejecuta las pruebas con interfaz fuera de pantalla."""
    raiz = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(raiz / "src"), str(raiz / "pruebas" / "unitarias")]
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    nombres = sys.argv[1:] or [
        "test_correccion_empaquetado", "test_vistas_deepseek_gemini",
        "test_trabajo_tabular", "test_reanudacion_consumidores",
        "test_seleccion_progreso_tabular", "test_respaldo_tabular_anterior", "test_mapeo_progreso_tabular",
        "test_integracion_salidas", "test_modo_ia_conversacional", "test_salidas_proceso",
        "test_rutas_salida", "test_regresiones_conexiones",
    ]
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in nombres)
    resultado = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if resultado.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
