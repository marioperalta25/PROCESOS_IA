"""Pruebas unitarias para los lectores de archivos por flujo (CSV y XLSX)."""

from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

import openpyxl

from procesos_ia.infraestructura.archivos.detector_formato import (
    detectar_codificacion,
    detectar_delimitador,
    detectar_encabezados,
)
from procesos_ia.infraestructura.archivos.fabrica_lectores import crear_lector_flujo
from procesos_ia.infraestructura.archivos.lector_csv import LectorCsv
from procesos_ia.infraestructura.archivos.lector_xlsx import LectorXlsx


class PruebaLectoresArchivos(unittest.TestCase):
    def setUp(self) -> None:
        self.directorio_temporal = tempfile.TemporaryDirectory()
        self.raiz = Path(self.directorio_temporal.name)

    def tearDown(self) -> None:
        self.directorio_temporal.cleanup()

    def test_deteccion_encabezados_y_lineas_vacias(self) -> None:
        filas = [
            ["", ""],  # linea vacia tipica de Excel
            ["id", "nombre", "descripcion"],
            ["1", "Juan", "Texto simple"],
            ["2", "Maria", "Otro texto"],
        ]
        inspeccion = detectar_encabezados(filas)
        self.assertTrue(inspeccion.tiene_encabezado)
        self.assertEqual(inspeccion.indice_fila_encabezado, 1)
        self.assertEqual(inspeccion.encabezados, ["id", "nombre", "descripcion"])

    def test_lector_csv_rfc4180_con_saltos_linea_en_comillas(self) -> None:
        ruta_csv = self.raiz / "prueba_rfc4180.csv"
        # CSV con salto de linea legitimo dentro de comillas
        contenido = (
            'id,comentario,categoria\n'
            '1,"Primera linea\nSegunda linea dentro de comilla",A\n'
            '2,"Comentario simple",B\n'
            '3,"Tercer comentario",C\n'
        )
        ruta_csv.write_text(contenido, encoding="utf-8")

        lector = LectorCsv()
        encabezados = lector.inicializar(ruta_csv)
        self.assertEqual(encabezados, ["id", "comentario", "categoria"])

        # Leer bloque saltando el registro 1
        bloque = list(lector.leer_bloque(tamano_bloque=5, saltar_hasta_indice=1))
        self.assertEqual(len(bloque), 2)

        reg2 = bloque[0]
        self.assertEqual(reg2.indice_fila, 2)
        self.assertEqual(reg2.valores_originales["comentario"], "Comentario simple")

        # Leer desde el inicio para verificar el campo multilínea
        todos = list(lector.leer_bloque(tamano_bloque=5, saltar_hasta_indice=0))
        self.assertEqual(len(todos), 3)
        self.assertIn("Segunda linea dentro de comilla", todos[0].valores_originales["comentario"])

    def test_lector_xlsx_flujo_y_salto(self) -> None:
        ruta_xlsx = self.raiz / "prueba_excel.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Datos"
        # Agregar cabecera y 3 filas
        ws.append(["codigo", "producto", "precio"])
        ws.append(["P01", "Monitor", "250"])
        ws.append(["P02", "Teclado", "45"])
        ws.append(["P03", "Raton", "20"])
        wb.save(str(ruta_xlsx))
        wb.close()

        lector = LectorXlsx()
        encabezados = lector.inicializar(ruta_xlsx)
        self.assertEqual(encabezados, ["codigo", "producto", "precio"])

        # Leer saltando hasta el registro 2 (debe entregar solo P03)
        bloque = list(lector.leer_bloque(tamano_bloque=10, saltar_hasta_indice=2))
        self.assertEqual(len(bloque), 1)
        self.assertEqual(bloque[0].indice_fila, 3)
        self.assertEqual(bloque[0].valores_originales["producto"], "Raton")

    def test_fabrica_lectores_instancia_correcta(self) -> None:
        csv_lector = crear_lector_flujo(Path("archivo.csv"))
        self.assertIsInstance(csv_lector, LectorCsv)

        xlsx_lector = crear_lector_flujo(Path("archivo.xlsx"))
        self.assertIsInstance(xlsx_lector, LectorXlsx)


if __name__ == "__main__":
    unittest.main()
