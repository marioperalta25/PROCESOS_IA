"""Pruebas unitarias de resolución y reutilización de subcarpetas de salida."""

import os
from pathlib import Path
import tempfile
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.rutas_salida import (
    resolver_subcarpeta_salida,
    sanitizar_nombre_subcarpeta,
)
from procesos_ia.interfaz.componentes.panel_archivos import PanelArchivos


class PruebaRutasSalida(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base = Path(self.temp_dir.name)

    def test_sanitizar_nombre_subcarpeta(self) -> None:
        self.assertEqual(sanitizar_nombre_subcarpeta("Mi Base 15/10/2026"), "Mi_Base_15_10_2026")
        self.assertEqual(sanitizar_nombre_subcarpeta("archivo.datos.csv"), "archivo.datos.csv")
        self.assertEqual(sanitizar_nombre_subcarpeta("   "), "trabajo")

    def test_genera_subcarpeta_con_fecha_si_no_existe(self) -> None:
        archivo = self.base / "clientes.csv"
        sub = resolver_subcarpeta_salida(self.base, archivo, fecha_hoy="20261022")
        self.assertEqual(sub, self.base / "clientes_20261022")

    def test_reutiliza_subcarpeta_existente_para_el_mismo_archivo(self) -> None:
        archivo = self.base / "clientes.csv"
        sub_existente = self.base / "clientes_20261020"
        sub_existente.mkdir(parents=True)

        # Al volver a procesar el mismo archivo, no debe crear clientes_20261022 sino reutilizar clientes_20261020
        sub_resuelta = resolver_subcarpeta_salida(self.base, archivo, fecha_hoy="20261022")
        self.assertEqual(sub_resuelta, sub_existente)

    def test_panel_archivos_actualiza_subcarpeta_al_cargar(self) -> None:
        panel = PanelArchivos()
        panel._directorio_base_salidas = self.base
        archivo = self.base / "contactos.csv"
        archivo.write_text("nombre,telefono\nJuan,123\n", encoding="utf-8")

        panel.cargar_archivo(archivo)
        self.assertTrue(str(panel.ruta_salida).startswith(str(self.base / "contactos_")))
        self.assertEqual(panel.input_salida.text(), str(panel.ruta_salida))

    def test_genera_copia_1_si_la_subcarpeta_ya_esta_completada(self) -> None:
        archivo = self.base / "clientes.csv"
        sub_inicial = self.base / "clientes_20261022"
        sub_inicial.mkdir(parents=True)
        # Simular trabajo finalizado en la carpeta inicial
        (sub_inicial / "resultado_procesado.csv").write_text("id,nombre\n1,Ana\n", encoding="utf-8")

        sub_resuelta = resolver_subcarpeta_salida(self.base, archivo, fecha_hoy="20261022")
        self.assertEqual(sub_resuelta, self.base / "clientes_20261022_copia_1")

    def test_genera_copia_2_si_copia_1_tambien_esta_completada(self) -> None:
        archivo = self.base / "clientes.csv"
        sub_inicial = self.base / "clientes_20261022"
        sub_inicial.mkdir(parents=True)
        (sub_inicial / "resultado_procesado.csv").write_text("id,nombre\n1,Ana\n", encoding="utf-8")

        sub_copia_1 = self.base / "clientes_20261022_copia_1"
        sub_copia_1.mkdir(parents=True)
        (sub_copia_1 / "resultado_procesado.csv").write_text("id,nombre\n1,Ana\n", encoding="utf-8")

        sub_resuelta = resolver_subcarpeta_salida(self.base, archivo, fecha_hoy="20261022")
        self.assertEqual(sub_resuelta, self.base / "clientes_20261022_copia_2")

    def test_enrutador_crea_jerarquia_base(self) -> None:
        enrutador = EnrutadorSalidas(directorio_raiz=self.base)
        self.assertEqual(enrutador.raiz, self.base)
        self.assertEqual(enrutador.datos, self.base / "datos")
        self.assertEqual(enrutador.imagenes, self.base / "imagenes")
        self.assertEqual(enrutador.plantillas, self.base / "plantillas")
        self.assertEqual(enrutador.analisis, self.base / "analisis")
        self.assertEqual(enrutador.conversaciones, self.base / "conversaciones")
        self.assertEqual(enrutador.extracciones, self.base / "extracciones")
        self.assertEqual(enrutador.reportes, self.base / "reportes")

        enrutador.asegurar_directorios()
        self.assertTrue(enrutador.datos.is_dir())
        self.assertTrue(enrutador.imagenes.is_dir())
        self.assertTrue(enrutador.plantillas.is_dir())
        self.assertTrue(enrutador.analisis.is_dir())
        self.assertTrue(enrutador.conversaciones.is_dir())
        self.assertTrue(enrutador.extracciones.is_dir())

    def test_enrutador_establecer_directorio_raiz(self) -> None:
        enrutador = EnrutadorSalidas(directorio_raiz=self.base)
        nueva = self.base / "nuevo_almacenamiento"
        enrutador.establecer_directorio_raiz(nueva)
        self.assertEqual(enrutador.raiz, nueva)
        self.assertTrue(enrutador.datos.is_dir())
        self.assertTrue(enrutador.imagenes.is_dir())
        self.assertTrue(enrutador.extracciones.is_dir())

    def test_enrutador_resuelve_subcarpeta_analisis(self) -> None:
        enrutador = EnrutadorSalidas(directorio_raiz=self.base)
        archivo = self.base / "datos.csv"
        sub = enrutador.resolver_subcarpeta_analisis(archivo, fecha_hoy="20261022")
        self.assertEqual(sub, self.base / "analisis" / "datos_20261022")

    def test_enrutador_resuelve_subcarpeta_modulo(self) -> None:
        enrutador = EnrutadorSalidas(directorio_raiz=self.base)
        sub = enrutador.resolver_subcarpeta_modulo(
            modulo="extracciones",
            nombre_trabajo="web_scraping.csv",
            fecha_hoy="20261022",
        )
        self.assertEqual(sub, self.base / "extracciones" / "web_scraping_20261022")

    def test_enrutador_migra_plantillas_previas(self) -> None:
        enrutador = EnrutadorSalidas(directorio_raiz=self.base / "salidas")
        directorio_previo = self.base / "prompts_antiguos"
        directorio_previo.mkdir(parents=True)
        (directorio_previo / "evaluar_latinos.md").write_text("# Prompt", encoding="utf-8")

        migrados = enrutador.migrar_plantillas_previas(directorio_previo=directorio_previo)
        self.assertEqual(len(migrados), 1)
        self.assertTrue((enrutador.plantillas / "evaluar_latinos.md").is_file())

    def test_panel_archivos_con_enrutador_inyectado(self) -> None:
        enrutador = EnrutadorSalidas(directorio_raiz=self.base)
        panel = PanelArchivos(enrutador=enrutador)
        archivo = self.base / "contactos.csv"
        archivo.write_text("nombre,telefono\nJuan,123\n", encoding="utf-8")

        panel.cargar_archivo(archivo)
        self.assertTrue(str(panel.ruta_salida).startswith(str(self.base / "analisis" / "contactos_")))
        self.assertEqual(panel.input_salida.text(), str(panel.ruta_salida))

