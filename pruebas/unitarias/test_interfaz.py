"""Pruebas unitarias para la interfaz gráfica de escritorio y sus componentes."""

from __future__ import annotations

import os
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

# Configurar plataforma offscreen para ejecucion de pruebas sin servidor X/pantalla grafica
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from procesos_ia.aplicacion.coordinador import CoordinadorTrabajo
from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
from procesos_ia.dominio.prompts import PlantillaPrompt
from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.ollama.modelos import (
    DiagnosticoOllama,
    EstadoServicioOllama,
    InformacionModelo,
)
from procesos_ia.interfaz.app import crear_aplicacion
from procesos_ia.interfaz.componentes.panel_archivos import PanelArchivos
from procesos_ia.interfaz.componentes.panel_configuracion import PanelConfiguracionIA
from procesos_ia.interfaz.componentes.panel_controles import PanelControles
from procesos_ia.interfaz.componentes.panel_encabezado import PanelEncabezado
from procesos_ia.interfaz.componentes.panel_telemetria import PanelTelemetria
from procesos_ia.interfaz.recursos import GestorRecursos
from procesos_ia.interfaz.ventana_principal import VentanaPrincipal


class PruebaInterfazEscritorio(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = crear_aplicacion([])

    def test_gestor_recursos_carga_rutas_validas(self) -> None:
        gestor = GestorRecursos()
        self.assertTrue(gestor.ruta_icono_aplicacion.name.endswith(".ico"))
        self.assertTrue(gestor.ruta_emblema_dragon.name.endswith(".png"))

        icono = gestor.obtener_icono_aplicacion()
        self.assertFalse(icono.isNull())

        pix = gestor.obtener_pixmap_emblema(48, 48)
        self.assertFalse(pix.isNull())

    def test_panel_encabezado_estados(self) -> None:
        panel = PanelEncabezado()

        diag_disp = DiagnosticoOllama(
            estado=EstadoServicioOllama.DISPONIBLE,
            version_cliente="0.24.0",
            version_servidor="0.4.1",
            ruta_ejecutable=Path("ollama.exe"),
            url_base="http://127.0.0.1:11434",
            mensaje="Activo",
        )
        panel.actualizar_estado_ollama(diag_disp)
        self.assertIn("DISPONIBLE", panel.badge_estado.text())

        diag_det = DiagnosticoOllama(
            estado=EstadoServicioOllama.DETENIDO,
            version_cliente="0.24.0",
            version_servidor=None,
            ruta_ejecutable=Path("ollama.exe"),
            url_base="http://127.0.0.1:11434",
            mensaje="Detenido",
        )
        panel.actualizar_estado_ollama(diag_det)
        self.assertIn("DETENIDO", panel.badge_estado.text())

    def test_panel_archivos_carga_y_seleccion_columnas(self) -> None:
        panel = PanelArchivos()
        ruta_csv = Path("pruebas/scratch_test.csv")
        ruta_csv.write_text("id,nombre,comentario\n1,Juan,Excelente servicio\n", encoding="utf-8")

        try:
            panel.cargar_archivo(ruta_csv)
            cols = panel.obtener_columnas_seleccionadas()
            self.assertEqual(cols, ["id", "nombre", "comentario"])
        finally:
            if ruta_csv.is_file():
                ruta_csv.unlink()

    def test_panel_configuracion_ia_modelos_y_prompts(self) -> None:
        panel = PanelConfiguracionIA()

        modelos = [
            InformacionModelo(
                nombre="qwen2.5:1.5b",
                tamano_bytes=1024**3,
                familia="qwen2",
                formato="gguf",
                parametros="1.5B",
                cuantizacion="Q4_K_M",
                modificado_utc="",
            )
        ]
        panel.actualizar_modelos(modelos)
        self.assertEqual(panel.modelo_seleccionado, "qwen2.5:1.5b")

        plantillas = [
            PlantillaPrompt(
                identificador="p1",
                titulo="Clasificador",
                descripcion="Clasifica textos",
                categoria="general",
                contenido="Instruccion del sistema",
            )
        ]
        panel.actualizar_prompts(plantillas)
        self.assertEqual(panel.prompt_sistema_seleccionado, "Instruccion del sistema")

    def test_panel_telemetria_actualizacion(self) -> None:
        panel = PanelTelemetria()
        panel.actualizar_fase("[EN PROCESO]")
        self.assertIn("[EN PROCESO]", panel.label_fase.text())

        panel.actualizar_progreso(procesadas=50, totales=100, ram_mb=128.5, velocidad=12.0)
        self.assertEqual(panel.barra_progreso.value(), 50)
        self.assertIn("50 / 100", panel.val_filas.text())
        self.assertIn("128.5 MB", panel.val_ram.text())
        self.assertIn("12.0 filas/s", panel.val_velocidad.text())

        panel.agregar_log("[INFO] Prueba log")
        self.assertIn("Prueba log", panel.texto_bitacora.toPlainText())

    def test_panel_controles_transiciones(self) -> None:
        panel = PanelControles()
        self.assertTrue(panel.btn_iniciar.isEnabled())
        self.assertFalse(panel.btn_pausar.isEnabled())
        self.assertFalse(panel.btn_cancelar.isEnabled())

        panel.configurar_estado_ejecucion(en_ejecucion=True)
        self.assertFalse(panel.btn_iniciar.isEnabled())
        self.assertTrue(panel.btn_pausar.isEnabled())
        self.assertTrue(panel.btn_cancelar.isEnabled())

    def test_ventana_principal_inicializacion(self) -> None:
        mock_cliente = MagicMock(spec=ClienteHttpOllama)
        mock_cliente.verificar_estado.return_value = DiagnosticoOllama(
            estado=EstadoServicioOllama.DISPONIBLE,
            version_cliente="0.24.0",
            version_servidor="0.4.1",
            ruta_ejecutable=Path("ollama.exe"),
            url_base="http://127.0.0.1:11434",
            mensaje="Activo",
        )
        mock_cliente.listar_modelos.return_value = []

        mock_coordinador = MagicMock(spec=CoordinadorTrabajo)
        mock_prompts = MagicMock(spec=ServicioCatalogoPrompts)
        mock_prompts.listar_plantillas.return_value = []

        ventana = VentanaPrincipal(
            coordinador=mock_coordinador,
            cliente_ollama=mock_cliente,
            servicio_prompts=mock_prompts,
        )
        self.assertIsNotNone(ventana)
        self.assertEqual(ventana.windowTitle(), "PROCESOS_IA - Enriquecimiento Masivo de Datos")


if __name__ == "__main__":
    unittest.main()
