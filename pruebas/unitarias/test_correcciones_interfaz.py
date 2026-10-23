"""Regresiones de seleccion, esquema, concurrencia y cierre cooperativo."""

from dataclasses import replace
import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QWidget

from procesos_ia.aplicacion.coordinador import CoordinadorTrabajo
from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.dominio.modelos import ConfiguracionTrabajo
from procesos_ia.dominio.prompts import PlantillaPrompt
from procesos_ia.interfaz.cierre import CierreCooperativo
from procesos_ia.interfaz.componentes.panel_configuracion import PanelConfiguracionIA
from procesos_ia.interfaz.ventana_principal import VentanaPrincipal


class HiloControlado(QObject):
    finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.activo = True
        self.cancelado = False

    def isRunning(self) -> bool:
        return self.activo

    def cancelar(self) -> None:
        self.cancelado = True

    def terminar(self) -> None:
        self.activo = False
        self.finished.emit()


class PruebaCorreccionesInterfaz(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_cambiar_a_plantilla_sin_esquema_limpia_columnas(self) -> None:
        panel = PanelConfiguracionIA()
        plantillas = [
            PlantillaPrompt("a", "A", "", "general", "A", columnas_salida=("clase",)),
            PlantillaPrompt("b", "B", "", "general", "B"),
        ]
        panel.actualizar_prompts(plantillas)
        panel.combo_prompts.setCurrentIndex(1)
        self.assertEqual(panel.columnas_salida_modelo, ())

    def test_usar_plantilla_selecciona_identificador_y_esquema(self) -> None:
        panel = PanelConfiguracionIA()
        plantillas = [
            PlantillaPrompt("a", "A", "", "general", "A", columnas_salida=("clase",)),
            PlantillaPrompt("b", "B", "", "general", "B", columnas_salida=("entidad",)),
        ]
        panel.actualizar_prompts(plantillas)
        ventana = MagicMock()
        ventana.panel_configuracion = panel
        ventana._servicio_prompts.listar_plantillas.return_value = plantillas
        ventana._cargar_catalogo_prompts = lambda: VentanaPrincipal._cargar_catalogo_prompts(ventana)
        VentanaPrincipal._al_seleccionar_plantilla(ventana, plantillas[1])
        self.assertEqual(panel.prompt_sistema_seleccionado, "B")
        self.assertEqual(panel.columnas_salida_modelo, ("entidad",))

    def test_esquema_vacio_falla_antes_de_abrir_archivos(self) -> None:
        config = ConfiguracionTrabajo(
            Path("entrada.csv"), Path("salida"), "simulado", 1, 1000, 512,
            0.1, 10.0, ("texto",), "Clasifica", "csv",
        )
        lector, escritor = MagicMock(), MagicMock()
        coordinador = CoordinadorTrabajo(
            lector, escritor, MagicMock(), MagicMock(), MagicMock(), config,
        )
        with self.assertRaises(ErrorProcesamiento):
            coordinador.iniciar_o_reanudar()
        lector.inicializar.assert_not_called()
        escritor.inicializar.assert_not_called()
        for columnas in (("clase", "clase"), ("estado_ia",), (" ",)):
            with self.subTest(columnas=columnas), self.assertRaises(ErrorProcesamiento):
                replace(config, columnas_salida_modelo=columnas).validar_esquema_salida()

    def test_cierre_espera_a_todos_sin_bloquear(self) -> None:
        ventana = QWidget()
        ventana.close = MagicMock()
        cierre = CierreCooperativo(ventana)
        trabajo, modelos = HiloControlado(), HiloControlado()
        evento = QCloseEvent()
        cierre.solicitar(evento, (trabajo, modelos))
        self.assertFalse(evento.isAccepted())
        self.assertTrue(trabajo.cancelado and modelos.cancelado)
        trabajo.terminar()
        self.app.processEvents()
        ventana.close.assert_not_called()
        modelos.terminar()
        self.app.processEvents()
        ventana.close.assert_called_once()

    def test_cierre_sin_hilos_acepta_evento(self) -> None:
        ventana = QWidget()
        evento = QCloseEvent()
        CierreCooperativo(ventana).solicitar(evento, (None,))
        self.assertTrue(evento.isAccepted())

    def test_clicks_repetidos_no_crean_mas_consultas(self) -> None:
        ventana = MagicMock()
        ventana._consulta_activa = False
        ventana._cierre.pendiente = False
        ventana._hilo_modelos = None
        with patch("procesos_ia.interfaz.ventana_principal.HiloListarModelos") as hilo:
            VentanaPrincipal._actualizar_modelos_segundo_plano(ventana, True)
            VentanaPrincipal._actualizar_modelos_segundo_plano(ventana, True)
            hilo.assert_called_once()
            hilo.return_value.start.assert_called_once()

    def test_error_de_listado_no_afirma_servicio_detenido(self) -> None:
        from procesos_ia.infraestructura.ollama.modelos import EstadoServicioOllama

        ventana = MagicMock()
        VentanaPrincipal._al_fallar_modelos(ventana, "HTTP 503")
        diag = ventana.panel_encabezado.actualizar_estado_ollama.call_args.args[0]
        self.assertEqual(diag.estado, EstadoServicioOllama.ERROR_CONEXION)
        self.assertEqual(diag.mensaje, "HTTP 503")
