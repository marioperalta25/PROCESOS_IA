"""Flujo de plantilla, vinculacion revisada, muestra y escritura real con LLM simulado."""

import csv
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtWidgets import QApplication

from procesos_ia.aplicacion.coordinador import CoordinadorTrabajo
from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
from procesos_ia.dominio.evaluaciones import DefinicionResultado
from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.dominio.modelos import ConfiguracionTrabajo
from procesos_ia.dominio.prompts import PlantillaPrompt, ResultadoRefinamiento
from procesos_ia.dominio.validador import ValidadorSemantico
from procesos_ia.infraestructura.archivos.lector_csv import LectorCsv
from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.ollama.servicio_inferencia import ServicioInferenciaOllama
from procesos_ia.infraestructura.persistencia.escritor_wal import EscritorWal
from procesos_ia.infraestructura.prompts.repositorio_md import RepositorioPromptsMd
from procesos_ia.interfaz.dialogo_preparacion import DialogoPrepararTrabajo
from procesos_ia.interfaz.dialogo_prompt import DialogoGestionPrompts


class PruebaPreparacionEvaluacion(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.raiz = Path(self.temporal.name)
        self.origen = self.raiz / "origen.csv"
        self.original = "comentario,nombre\nHola,Original1\nGood morning,Original2\n"
        self.origen.write_text(self.original, encoding="utf-8")
        self.resultado = DefinicionResultado(
            "idioma", "Idioma del comentario", ("texto",), "texto", ("espanol", "otro"),
        )
        self.plantilla = PlantillaPrompt("idioma", "Idioma", "", "General", "Evalua idioma", resultados=(self.resultado,))
        self.config = ConfiguracionTrabajo(
            self.origen, self.raiz / "salida", "simulado", 2, 1000, 512, 0.0, 10.0,
            ("comentario",), self.plantilla.contenido, "csv", ("idioma",),
        )
        self.cliente = MagicMock(spec=ClienteHttpOllama)
        self.cliente.generar_estructurado.side_effect = [{"idioma": "espanol"}, {"idioma": "otro"}]
        self.inferencia = ServicioInferenciaOllama(self.cliente)

    def _dialogo(self):
        return DialogoPrepararTrabajo(self.config, self.plantilla, ("comentario", "nombre"), self.inferencia)

    def _vincular(self, dialogo):
        dialogo.entradas["texto"].item(0).setCheckState(Qt.CheckState.Checked)
        dialogo.salidas["idioma"].setText("hablaespanolIA")

    def _esperar(self, hilo):
        bucle = QEventLoop()
        terminados = []
        hilo.finished.connect(lambda: terminados.append(True))
        hilo.finished.connect(bucle.quit)
        QTimer.singleShot(2000, bucle.quit)
        ya_terminado = not hilo.isRunning()
        if not ya_terminado:
            bucle.exec()
        self.app.processEvents()
        self.assertTrue(ya_terminado or terminados)

    def test_usuario_debe_confirmar_vinculos_no_deducidos(self) -> None:
        dialogo = self._dialogo()
        with self.assertRaises(ErrorProcesamiento):
            dialogo.obtener_configuracion()
        self._vincular(dialogo)
        dialogo.accept()
        contrato = dialogo.configuracion_aprobada.obtener_contrato()
        self.assertEqual(contrato.entradas[0].columnas, ("comentario",))
        self.assertEqual(contrato.salidas[0].columna, "hablaespanolIA")

    def test_no_aprueba_destino_que_sobrescribe_columna_no_enviada(self) -> None:
        dialogo = self._dialogo()
        self._vincular(dialogo)
        dialogo.salidas["idioma"].setText("nombre")
        dialogo.accept()
        self.assertIsNone(dialogo.configuracion_aprobada)
        self.assertIn("sobrescribiria", dialogo.estado.text())

    def test_muestra_en_hilo_no_crea_salidas_y_se_invalida_al_editar(self) -> None:
        dialogo = self._dialogo()
        self._vincular(dialogo)
        dialogo._probar_muestra()
        hilo = dialogo._hilo
        self._esperar(hilo)
        self.assertEqual(dialogo.tabla_muestra.rowCount(), 2)
        self.assertIn("espanol", dialogo.tabla_muestra.item(0, 2).text())
        self.assertIn("otro", dialogo.tabla_muestra.item(1, 2).text())
        self.assertFalse(self.config.directorio_salida.exists())
        dialogo.salidas["idioma"].setText("idioma_revisado_ia")
        self.assertEqual(dialogo.tabla_muestra.rowCount(), 0)
        self.assertEqual(self.origen.read_text(encoding="utf-8"), self.original)

    def test_fila_invalida_no_desplaza_resultado_de_la_siguiente(self) -> None:
        dialogo = self._dialogo()
        self._vincular(dialogo)
        config = dialogo.obtener_configuracion()
        self.cliente.generar_estructurado.side_effect = [{"idioma": None}, {"idioma": "otro"}]
        coordinador = CoordinadorTrabajo(
            LectorCsv(), EscritorWal(), self.inferencia,
            ValidadorSemantico(contrato=config.obtener_contrato()), MagicMock(), config,
        )
        try:
            coordinador.iniciar_o_reanudar()
            coordinador.procesar_siguiente_lote()
        finally:
            coordinador.cerrar()
        ruta = config.directorio_salida / "resultado_procesado.csv"
        with ruta.open(encoding="utf-8", newline="") as archivo:
            filas = list(csv.DictReader(archivo))
        self.assertEqual([(f["nombre"], f["estado_ia"], f["hablaespanolIA"]) for f in filas], [
            ("Original1", "error", ""), ("Original2", "exito", "otro"),
        ])
        contenido = ruta.read_bytes()
        cambiado = CoordinadorTrabajo(
            LectorCsv(), EscritorWal(), self.inferencia, MagicMock(), MagicMock(),
            replace(config, prompt_sistema="Otra tarea"),
        )
        try:
            with self.assertRaisesRegex(ErrorProcesamiento, "otro trabajo"):
                cambiado.iniciar_o_reanudar()
        finally:
            cambiado.cerrar()
        self.assertEqual(ruta.read_bytes(), contenido)

    def test_escritura_conserva_filas_originales_y_destinos(self) -> None:
        dialogo = self._dialogo()
        self._vincular(dialogo)
        config = dialogo.obtener_configuracion()
        coordinador = CoordinadorTrabajo(
            LectorCsv(), EscritorWal(), self.inferencia,
            ValidadorSemantico(contrato=config.obtener_contrato()), MagicMock(), config,
        )
        try:
            coordinador.iniciar_o_reanudar()
            while coordinador.procesar_siguiente_lote():
                pass
        finally:
            coordinador.cerrar()
        with (config.directorio_salida / "resultado_procesado.csv").open(encoding="utf-8", newline="") as archivo:
            filas = list(csv.DictReader(archivo))
        self.assertEqual([(f["nombre"], f["hablaespanolIA"]) for f in filas], [
            ("Original1", "espanol"), ("Original2", "otro"),
        ])
        self.assertEqual(self.origen.read_text(encoding="utf-8"), self.original)

    def test_editor_genera_y_guarda_criterios_sin_encabezados(self) -> None:
        repo = RepositorioPromptsMd(self.raiz / "prompts")
        motor = MagicMock()
        motor.refinar_prompt.return_value = ResultadoRefinamiento(
            "Evalua idioma con evidencia", ("idioma",), "Revisar", (self.resultado,),
        )
        servicio = ServicioCatalogoPrompts(repo, motor)
        dialogo = DialogoGestionPrompts(servicio, "simulado")
        dialogo._crear_nuevo()
        dialogo.input_titulo.setText("Idioma revisado")
        dialogo.texto_contenido.setPlainText("Quiero evaluar el idioma del texto")
        dialogo._refinar_con_ia()
        self._esperar(dialogo._hilo_refinamiento)
        self.assertEqual(dialogo.editor_resultados.obtener(), (self.resultado,))
        recibidas = []
        dialogo.plantilla_seleccionada.connect(recibidas.append)
        dialogo._usar_plantilla()
        guardada = servicio.obtener_plantilla(recibidas[0].identificador)
        self.assertEqual(guardada.resultados, (self.resultado,))
        self.assertEqual(guardada.columnas_requeridas, ())
        peticion = motor.refinar_prompt.call_args.args[0]
        self.assertEqual(peticion.columnas_entrada, ())

    def test_refinador_valida_idea_vacia(self) -> None:
        repo = RepositorioPromptsMd(self.raiz / "prompts")
        servicio = ServicioCatalogoPrompts(repo, MagicMock())
        dialogo = DialogoGestionPrompts(servicio, "simulado")
        dialogo._crear_nuevo()
        dialogo.texto_contenido.clear()
        dialogo._refinar_con_ia()
        self.assertIsNone(dialogo._hilo_refinamiento)
        self.assertIn("[ALERTA]", dialogo.estado_refinamiento.text())
