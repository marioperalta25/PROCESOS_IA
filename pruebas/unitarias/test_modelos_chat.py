"""Modelo fijo por chat, migración compatible y mensajes diferenciados."""

import json
import os
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTextEdit

from procesos_ia.aplicacion.conversacion import ServicioConversacion
from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.infraestructura.ollama.parametros_chat import cargar_parametros_chat
from procesos_ia.infraestructura.ollama.preparador_chat import PreparadorChatOllama
from procesos_ia.infraestructura.persistencia.repositorio_chat import RepositorioChat
from procesos_ia.interfaz.vista_chat import VistaChat


class PruebaModelosChat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.parametros = cargar_parametros_chat()
        self.repo = RepositorioChat(Path(temporal.name), self.parametros)
        self.generar = MagicMock(return_value="Texto literal <b>sin HTML</b>")
        self.servicio = ServicioConversacion(self.repo, self.generar, self.parametros)
        self.modelos = ["modelo-A", "modelo-B"]
        self.vista = VistaChat(self.servicio, self.parametros, lambda: ("modelo-A", 4096, 0.1),
                               lambda: False, catalogo=lambda: self.modelos)
        self.addCleanup(self.vista.deleteLater)

    def esperar(self, condicion):
        for _ in range(300):
            self.app.processEvents()
            if condicion():
                return
            QTest.qWait(10)
        self.fail("La tarea no finalizó")

    def enviar(self, texto="Hola"):
        self.vista.entrada.setPlainText(texto)
        self.vista._enviar()
        self.esperar(lambda: self.vista._hilo is None)

    def test_elegir_no_infiere_y_primer_envio_fija_y_persiste_modelo(self):
        self.vista.combo_modelos.setCurrentIndex(self.vista.combo_modelos.findData("modelo-B"))
        self.generar.assert_not_called()
        self.assertFalse(self.repo.existe(self.vista._datos["id"]))
        self.enviar()
        self.assertEqual(self.generar.call_args.args[1], "modelo-B")
        guardado = self.repo.leer(self.vista._datos["id"])
        self.assertEqual(guardado["modelo"], "modelo-B")
        self.assertEqual(guardado["mensajes"][-1]["modelo"], "modelo-B")
        self.assertFalse(self.vista.combo_modelos.isEnabled())
        self.vista._opciones = lambda: ("otro-inicio", 8192, 0.9)
        self.enviar("Segunda pregunta")
        self.assertEqual(self.generar.call_args.args[1:4], ("modelo-B", 4096, 0.1))

    def test_otra_conversacion_permite_otro_modelo_sin_contexto_heredado(self):
        self.enviar("Información exclusiva de A")
        anterior = self.vista._datos["id"]
        self.vista._editar_memoria()
        self.vista.resumen.setPlainText("RESUMEN EXCLUSIVO A")
        self.vista._confirmar_edicion()
        self.vista._nuevo()
        self.assertTrue(self.vista.combo_modelos.isEnabled())
        self.assertEqual(self.vista._datos["mensajes"], [])
        self.assertEqual(self.vista._datos["resumen"], "")
        self.vista.combo_modelos.setCurrentIndex(self.vista.combo_modelos.findData("modelo-B"))
        self.enviar("Primera pregunta en B")
        mensajes = self.generar.call_args.args[0]
        self.assertNotIn("EXCLUSIVO", json.dumps(mensajes))
        self.assertNotIn("Información exclusiva de A", json.dumps(mensajes, ensure_ascii=False))
        fila = next(i for i in range(self.vista.lista.count())
                    if self.vista.lista.item(i).data(Qt.ItemDataRole.UserRole) == anterior)
        self.vista.lista.setCurrentRow(fila)
        self.assertEqual(self.vista.combo_modelos.currentData(), "modelo-A")
        self.assertFalse(self.vista.combo_modelos.isEnabled())

    def test_fallo_posterior_al_guardado_y_reintento_conservan_modelo(self):
        self.generar.side_effect = ErrorProcesamiento("Fallo de prueba")
        self.enviar()
        self.assertFalse(self.vista.combo_modelos.isEnabled())
        self.assertEqual(self.vista._datos["modelo"], "modelo-A")
        self.assertEqual(len(self.vista._datos["mensajes"]), 1)
        with self.assertRaises(ErrorProcesamiento):
            self.servicio.responder(self.vista._datos, "Hola", "modelo-B", 4096, 0.1, Event(), True)
        self.generar.side_effect = None
        self.vista._enviar(reintentar=True)
        self.esperar(lambda: self.vista._hilo is None)
        self.assertEqual(len(self.vista._datos["mensajes"]), 2)

    def test_catalogo_sin_modelo_guardado_no_sustituye_ni_envia(self):
        self.enviar()
        self.modelos.remove("modelo-A")
        self.vista._pintar()
        self.assertEqual(self.vista.combo_modelos.currentData(), "modelo-A")
        self.generar.reset_mock()
        self.vista.entrada.setPlainText("Conservar borrador")
        self.vista._enviar()
        self.generar.assert_not_called()
        self.assertEqual(self.vista.entrada.toPlainText(), "Conservar borrador")
        self.assertIn(self.parametros["textos"]["modelo_ausente"], self.vista.banner.texto)

    def test_historial_antiguo_legible_sin_atribuir_modelo_ni_reescribir(self):
        self.enviar()
        identidad = self.vista._datos["id"]
        datos = self.repo.leer(identidad)
        datos.pop("modelo")
        for mensaje in datos["mensajes"]:
            mensaje.pop("modelo", None)
        ruta = self.repo._ruta(identidad)
        ruta.write_text(json.dumps(datos), encoding="utf-8")
        original = ruta.read_bytes()
        self.vista._datos = self.repo.leer(identidad)
        self.vista._pintar()
        self.generar.reset_mock()
        self.vista.entrada.setPlainText("No enviar")
        self.vista._enviar()
        self.generar.assert_not_called()
        self.assertEqual(ruta.read_bytes(), original)
        self.assertIn("Modelo no registrado", self.vista.transcripcion.toPlainText())

    def test_repositorio_rechaza_sustituir_modelo_de_chat_iniciado(self):
        self.enviar()
        datos = self.repo.leer(self.vista._datos["id"])
        datos["modelo"] = "modelo-B"
        with self.assertRaises(ErrorProcesamiento):
            self.repo.guardar(datos)

    def test_burbujas_lados_texto_literal_y_limite_visible(self):
        self.vista.resize(700, 600)
        self.vista.show()
        self.enviar("<script>Texto del usuario</script>")
        for _ in range(5):
            self.app.processEvents()
        panel = self.vista.transcripcion
        usuario, asistente = [b for b, _ in panel._burbujas]
        self.assertEqual(usuario.objectName(), "burbuja_usuario")
        self.assertEqual(asistente.objectName(), "burbuja_asistente")
        self.assertGreater(usuario.x(), asistente.x())
        self.assertIn("<script>", usuario.findChild(QTextEdit).toPlainText())
        self.assertIn("<b>sin HTML</b>", asistente.findChild(QTextEdit).toPlainText())
        self.assertFalse(usuario.findChild(QTextEdit).acceptRichText())
        self.vista.close()

    def test_preparador_cachea_solo_metadatos_e_invalida_sin_generar(self):
        cliente = MagicMock()
        cliente.url_base = "http://ejemplo.invalid"
        cliente._ejecutar_solicitud_json.return_value = {
            "capabilities": ["completion"], "license": "No retener",
            "model_info": {"general.architecture": "prueba", "prueba.context_length": 2048},
        }
        preparador = PreparadorChatOllama(cliente, self.parametros)
        self.assertEqual(preparador.preparar("modelo-A", 4096), 2048)
        self.assertEqual(preparador.preparar("modelo-A", 1024), 1024)
        self.assertEqual(cliente._ejecutar_solicitud_json.call_count, 1)
        self.assertNotIn("No retener", str(preparador._cache))
        self.assertTrue(cliente._ejecutar_solicitud_json.call_args.args[0].endswith("/api/show"))
        preparador.invalidar()
        preparador.preparar("modelo-A", 2048)
        self.assertEqual(cliente._ejecutar_solicitud_json.call_count, 2)

    def test_capacidad_incompatible_falla_sin_inferencia_ni_archivos(self):
        cliente = MagicMock()
        cliente.url_base = "http://ejemplo.invalid"
        cliente._ejecutar_solicitud_json.return_value = {"capabilities": ["embedding"]}
        self.servicio._preparar_modelo = PreparadorChatOllama(cliente, self.parametros).preparar
        self.enviar()
        self.generar.assert_not_called()
        self.assertFalse(self.repo.existe(self.vista._datos["id"]))
        self.assertTrue(self.vista.combo_modelos.isEnabled())

    def test_contexto_declarado_menor_se_aplica_y_se_explica(self):
        self.servicio._preparar_modelo = lambda nombre, contexto: min(contexto, 2048)
        self.enviar()
        self.assertEqual(self.generar.call_args.args[2], 2048)
        self.assertEqual(self.vista._datos["contexto"], 2048)
        self.assertIn("2048", self.vista.banner.texto)

    def test_modelo_elegido_se_conserva_en_borrador_y_no_carga_datos(self):
        self.vista.combo_modelos.setCurrentIndex(self.vista.combo_modelos.findData("modelo-B"))
        identidad = self.vista._datos["id"]
        self.vista.entrada.setPlainText("Borrador con modelo B")
        self.vista._nuevo()
        fila = next(i for i in range(self.vista.lista.count())
                    if self.vista.lista.item(i).data(Qt.ItemDataRole.UserRole) == identidad)
        self.vista.lista.setCurrentRow(fila)
        self.assertEqual(self.vista.combo_modelos.currentData(), "modelo-B")
        self.assertTrue(self.vista.combo_modelos.isEnabled())
        self.generar.assert_not_called()

    def test_selector_bloqueado_mientras_se_envia_y_respuesta_no_cambia_modelo(self):
        iniciado, liberar = Event(), Event()
        def generar(*args, **kwargs):
            iniciado.set()
            liberar.wait(2)
            return "Respuesta de A"
        self.generar.side_effect = generar
        self.vista.entrada.setPlainText("Una pregunta")
        self.vista._enviar()
        self.esperar(iniciado.is_set)
        self.assertFalse(self.vista.combo_modelos.isEnabled())
        self.vista.combo_modelos.setCurrentIndex(self.vista.combo_modelos.findData("modelo-B"))
        self.assertEqual(self.vista._datos["modelo"], "modelo-A")
        liberar.set()
        self.esperar(lambda: self.vista._hilo is None)
        self.assertEqual(self.vista._datos["mensajes"][-1]["modelo"], "modelo-A")
