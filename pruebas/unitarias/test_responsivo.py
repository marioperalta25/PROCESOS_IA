"""Pruebas unitarias de adaptación responsiva según el tamaño de la ventana."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QSize
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QApplication, QTableWidget

from procesos_ia.interfaz.componentes.panel_archivos import PanelArchivos
from procesos_ia.interfaz.componentes.panel_encabezado import PanelEncabezado
from procesos_ia.interfaz.componentes.panel_configuracion import PanelConfiguracionIA
from procesos_ia.interfaz.componentes.panel_telemetria import PanelTelemetria
from procesos_ia.interfaz.componentes.panel_controles import PanelControles
from procesos_ia.interfaz.responsivo import (
    ModoPantalla,
    configurar_tabla_responsiva,
    determinar_modo_pantalla,
)
from procesos_ia.interfaz.ventana_principal import VentanaPrincipal


class PruebaResponsivo(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.raiz = Path(self.temp_dir.name)

    def test_clasificacion_modo_pantalla(self) -> None:
        self.assertEqual(determinar_modo_pantalla(700), ModoPantalla.COMPACTO)
        self.assertEqual(determinar_modo_pantalla(819), ModoPantalla.COMPACTO)
        self.assertEqual(determinar_modo_pantalla(820), ModoPantalla.ESTANDAR)
        self.assertEqual(determinar_modo_pantalla(1200), ModoPantalla.ESTANDAR)
        self.assertEqual(determinar_modo_pantalla(1250), ModoPantalla.AMPLIO)
        self.assertEqual(determinar_modo_pantalla(1920), ModoPantalla.AMPLIO)

    def test_configurar_tabla_responsiva(self) -> None:
        tabla = QTableWidget(2, 3)
        configurar_tabla_responsiva(tabla, columnas_fijas={0: 60}, columna_expandible=1)
        self.assertEqual(tabla.columnWidth(0), 60)

    def test_panel_encabezado_adapta_modo(self) -> None:
        panel = PanelEncabezado()
        panel.adaptar_modo(ModoPantalla.COMPACTO)
        self.assertTrue(panel.label_subtitulo.isHidden())
        self.assertEqual(panel.btn_refrescar.text(), "Reconectar")

        panel.adaptar_modo(ModoPantalla.ESTANDAR)
        self.assertFalse(panel.label_subtitulo.isHidden())
        self.assertEqual(panel.btn_refrescar.text(), "Conectar / Iniciar Ollama")

    def test_panel_telemetria_adapta_columnas(self) -> None:
        panel = PanelTelemetria()
        # En modo compacto son 4 filas por 2 columnas
        panel.adaptar_modo(ModoPantalla.COMPACTO)
        self.assertIsNotNone(panel.layout_metricas.itemAtPosition(0, 0))
        self.assertIsNotNone(panel.layout_metricas.itemAtPosition(3, 1))

        # En modo estandar son 2 filas por 4 columnas
        panel.adaptar_modo(ModoPantalla.ESTANDAR)
        self.assertIsNotNone(panel.layout_metricas.itemAtPosition(0, 2))
        self.assertIsNotNone(panel.layout_metricas.itemAtPosition(1, 3))

    def test_panel_configuracion_adapta_grilla(self) -> None:
        panel = PanelConfiguracionIA()
        panel.adaptar_modo(ModoPantalla.COMPACTO)
        self.assertIsNotNone(panel.layout_params.itemAtPosition(4, 0))

        panel.adaptar_modo(ModoPantalla.ESTANDAR)
        self.assertIsNotNone(panel.layout_params.itemAtPosition(0, 2))

    def test_panel_controles_adapta_textos(self) -> None:
        panel = PanelControles()
        panel.adaptar_modo(ModoPantalla.COMPACTO)
        self.assertEqual(panel.btn_iniciar.text(), "Iniciar")
        self.assertEqual(panel.btn_memoria.text(), "VRAM")

        panel.adaptar_modo(ModoPantalla.ESTANDAR)
        self.assertEqual(panel.btn_iniciar.text(), "Iniciar Procesamiento")
        self.assertEqual(panel.btn_memoria.text(), "Liberar VRAM")

        panel.adaptar_modo(ModoPantalla.AMPLIO)
        self.assertEqual(panel.btn_iniciar.maximumWidth(), 320)
        self.assertEqual(panel.btn_pausar.maximumWidth(), 180)

    def test_panel_archivos_adapta_modo(self) -> None:
        panel = PanelArchivos()
        panel.adaptar_modo(ModoPantalla.COMPACTO)
        self.assertEqual(panel.btn_examinar_entrada.text(), "...")
        self.assertEqual(panel.btn_examinar_entrada.maximumWidth(), 60)

        panel.adaptar_modo(ModoPantalla.ESTANDAR)
        self.assertEqual(panel.btn_examinar_entrada.text(), "Examinar...")
        self.assertEqual(panel.btn_examinar_entrada.maximumWidth(), 130)

        panel.adaptar_modo(ModoPantalla.AMPLIO)
        self.assertEqual(panel.btn_examinar_entrada.text(), "Examinar...")
        self.assertEqual(panel.btn_examinar_entrada.maximumWidth(), 150)

    def test_ventana_principal_responde_a_redimensionamiento(self) -> None:
        ventana = VentanaPrincipal(
            coordinador=MagicMock(),
            cliente_ollama=MagicMock(),
            servicio_prompts=MagicMock(),
            directorio_base=self.raiz,
        )
        # Redimensionar a compacto (750x600)
        evento_compacto = QResizeEvent(QSize(750, 600), QSize(840, 780))
        ventana.resizeEvent(evento_compacto)
        self.assertEqual(ventana.panel_controles.btn_iniciar.text(), "Iniciar")

        # Redimensionar a estándar (1000x800)
        evento_estandar = QResizeEvent(QSize(1000, 800), QSize(750, 600))
        ventana.resizeEvent(evento_estandar)
        self.assertEqual(ventana.panel_controles.btn_iniciar.text(), "Iniciar Procesamiento")
