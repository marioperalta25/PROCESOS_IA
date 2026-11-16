"""La seleccion del original resuelve el progreso sin exigir otro archivo al usuario."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.comun.gestor_reanudacion_tabular import GestorReanudacionTabular
from procesos_ia.dominio.reanudacion import AccionReanudacion
from procesos_ia.infraestructura.archivos.escritor_csv import guardar_filas_csv
from procesos_ia.interfaz.ia_web.vistas.vista_ia_general import VistaIAGeneral


class PruebaSeleccionProgresoTabular(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)
        self.enrutador = EnrutadorSalidas(self.raiz / "salidas")
        self.origen = self.raiz / "original.csv"
        self.filas = [{"nombre": "Ana"}, {"nombre": "Beto"}, {"nombre": "Carla"}]
        guardar_filas_csv(self.filas, self.origen)
        trabajo = GestorReanudacionTabular(self.enrutador).preparar_trabajo(
            self.origen, "modo_ia", "Evaluar", ["nombre"], self.filas, {"hoja": None},
        )
        with trabajo.abrir(self.enrutador, "resultado.csv"):
            trabajo.confirmar([{**trabajo.filas[0], "_estado_ia": "EXITOSO", "evaluacion_ia": "Anterior"}])
            self.salida_anterior = trabajo.finalizar("cancelados")
        self.vista = VistaIAGeneral(gestor_sesion=MagicMock(), enrutador=self.enrutador)
        self.addCleanup(self.vista.close)
        self.vista.panel_modo_chat.cargar_archivo(self.origen)
        self.vista.panel_modo_chat.txt_instrucciones.setPlainText("Evaluar")

    def test_continuar_resuelve_la_copia_sin_moverla_en_la_interfaz(self):
        with patch("procesos_ia.interfaz.comun.preparacion_tabular.solicitar_decision_reanudacion", return_value=AccionReanudacion.SOLO_PENDIENTES):
            tipo, parametros = self.vista._resolver_modo_ia()
        self.assertEqual(tipo, "modo_ia_lote")
        self.assertEqual([f["_id_registro"] for f in parametros["filas"]], ["fila_2", "fila_3"])
        self.assertEqual(parametros["trabajo_tabular"].respaldo.parent.parent, self.salida_anterior.parent)
        self.assertEqual(self.vista.panel_modo_chat.obtener_ruta_archivo(), self.origen)
        self.assertTrue(self.salida_anterior.exists())

    def test_cancelar_dialogo_no_mueve_ni_reinicia_el_respaldo(self):
        contenido = self.salida_anterior.read_bytes()
        with patch("procesos_ia.interfaz.comun.preparacion_tabular.solicitar_decision_reanudacion", return_value=AccionReanudacion.CANCELAR):
            self.assertIsNone(self.vista._resolver_modo_ia())
        self.assertEqual(self.salida_anterior.read_bytes(), contenido)

    def test_cambiar_plantilla_prepara_otro_trabajo(self):
        self.vista.panel_modo_chat.txt_instrucciones.setPlainText("Otra plantilla")
        with patch("procesos_ia.interfaz.comun.preparacion_tabular.solicitar_decision_reanudacion") as dialogo:
            _, parametros = self.vista._resolver_modo_ia()
        dialogo.assert_not_called()
        self.assertIsNone(parametros["trabajo_tabular"].respaldo)
        self.assertEqual(len(parametros["filas"]), 3)

    def test_respaldo_perdido_se_informa_sin_comenzar_desde_cero(self):
        progreso = self.salida_anterior.parent / ".estado" / "progreso_tabular.csv"
        progreso.unlink()
        with patch("procesos_ia.interfaz.comun.preparacion_tabular.QMessageBox.warning") as advertencia:
            self.assertIsNone(self.vista._resolver_modo_ia())
        advertencia.assert_called_once()
        self.assertTrue(self.salida_anterior.exists())

    def test_no_habilita_otra_ejecucion_mientras_termina_la_cancelacion(self):
        hilo = MagicMock()
        hilo.isRunning.return_value = True
        self.vista._hilo = hilo
        self.vista._cancelando = True
        self.vista.btn_ejecutar.setEnabled(False)
        self.vista._restablecer_botones_cancelacion()
        self.assertFalse(self.vista.btn_ejecutar.isEnabled())
        self.assertTrue(self.vista._cancelando)
