"""Recuerdos elegidos por el usuario, selección literal y aislamiento por chat."""

import os
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from procesos_ia.aplicacion.conversacion import ServicioConversacion
from procesos_ia.infraestructura.ollama.parametros_chat import cargar_parametros_chat
from procesos_ia.infraestructura.persistencia.repositorio_chat import RepositorioChat
from procesos_ia.interfaz.mensajes_chat import TextoMensaje
from procesos_ia.interfaz.vista_chat import VistaChat


class PruebaMemoriaFijada(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.p = cargar_parametros_chat()
        self.repo = RepositorioChat(Path(temporal.name), self.p)
        self.generar = MagicMock(return_value="Respuesta de prueba")
        self.s = ServicioConversacion(self.repo, self.generar, self.p)
        self.vista = VistaChat(self.s, self.p, lambda: ("simulado", 2048, 0.1), lambda: False)
        self.addCleanup(self.vista.deleteLater)

    def enviar(self, texto):
        self.vista.entrada.setPlainText(texto)
        self.vista._enviar()
        for _ in range(300):
            self.app.processEvents()
            if self.vista._hilo is None:
                return
            QTest.qWait(10)
        self.fail("La tarea no terminó")

    def boton(self, indice=0):
        return self.vista.transcripcion._burbujas[indice][0].findChild(QPushButton, "recordar_mensaje")

    def test_recordar_sin_inferencia_y_conservar_nombre_tras_recortar_historial(self):
        self.enviar("Me llamo Irene")
        self.generar.reset_mock()
        self.boton().click()
        datos = self.repo.leer(self.vista._datos["id"])
        self.assertEqual(datos["resumen"], "Usuario: Me llamo Irene")
        self.generar.assert_not_called()
        for i in range(10):
            for rol in ("user", "assistant"):
                datos["mensajes"].append({"id": f"{i}-{rol}", "rol": rol,
                                           "texto": str(i) * 400, "estado": "completo"})
        self.repo.guardar(datos)
        self.s.responder(datos, "¿Cuál es mi nombre?", "simulado", 2048, 0.1, Event())
        contexto = self.generar.call_args.args[0]
        self.assertIn("Usuario: Me llamo Irene", contexto[1]["content"])
        self.assertNotIn("Me llamo Irene", [m["content"] for m in contexto[2:]])
        self.generar.assert_called_once()

    def test_seleccion_guarda_solo_fragmento_y_no_duplica_al_repetir(self):
        self.enviar("Me llamo Irene. Trabajo en diseño.")
        cuerpo = self.vista.transcripcion._burbujas[0][0].findChild(TextoMensaje)
        cursor = cuerpo.textCursor()
        cursor.setPosition(9)
        cursor.setPosition(14, QTextCursor.MoveMode.KeepAnchor)
        cuerpo.setTextCursor(cursor)
        self.boton().click()
        self.assertEqual(self.vista._datos["resumen"], "Usuario: Irene")
        version = self.vista._datos["actualizado"]
        self.boton().click()
        self.assertEqual(self.vista._datos["actualizado"], version)
        self.assertEqual(self.vista._datos["resumen"].count("Irene"), 1)

    def test_modelo_requiere_accion_explicita_y_conserva_su_origen(self):
        self.enviar("Una consulta")
        self.assertEqual(self.vista._datos["resumen"], "")
        self.generar.reset_mock()
        self.boton(1).click()
        self.assertEqual(self.vista._datos["resumen"],
                         "Modelo (seleccionado por el usuario): Respuesta de prueba")
        self.generar.assert_not_called()

    def test_texto_extenso_abre_editor_expandible_sin_guardarlo_y_permite_abreviar(self):
        self.enviar("a" * 1800)
        original = self.repo.leer(self.vista._datos["id"])
        self.boton().click()
        self.assertIs(self.vista.contenido.currentWidget(), self.vista.editor)
        self.assertIn("a" * 1800, self.vista.resumen.toPlainText())
        self.assertEqual(self.repo.leer(original["id"]), original)
        alto = self.vista.resumen.editor.height()
        self.vista.resumen._expandir_altura()
        self.assertGreater(self.vista.resumen.editor.height(), alto)
        self.vista.resumen.setPlainText("Objetivo: probar la memoria breve.")
        self.vista._confirmar_edicion()
        self.assertEqual(self.repo.leer(original["id"])["resumen"], "Objetivo: probar la memoria breve.")

    def test_otro_chat_no_recibe_recuerdos_ni_senales_de_botones_antiguos(self):
        self.enviar("Dato exclusivo A")
        mensaje = self.vista._datos["mensajes"][0]
        self.boton().click()
        self.vista._nuevo()
        self.enviar("Chat B")
        self.vista._memoria.recordar(mensaje["id"], mensaje["texto"])
        self.assertEqual(self.vista._datos["resumen"], "")
        self.assertNotIn("Dato exclusivo A", str(self.generar.call_args.args[0]))

    def test_ocupado_deshabilita_recordar_y_fragmentos_no_crean_recuerdos(self):
        self.enviar("Dato")
        self.vista._hilo = object()
        try:
            self.vista._pintar()
            self.assertFalse(self.boton().isEnabled())
            mensaje = self.vista._datos["mensajes"][0]
            self.vista._memoria.recordar(mensaje["id"], mensaje["texto"])
            self.assertEqual(self.vista._datos["resumen"], "")
        finally:
            self.vista._hilo = None

    def test_conflicto_de_version_no_sobrescribe_memoria_ajena(self):
        self.enviar("Dato")
        vigente = self.repo.leer(self.vista._datos["id"])
        vigente["resumen"] = "Cambio de otra instancia"
        self.repo.guardar(vigente)
        self.boton().click()
        self.assertEqual(self.repo.leer(vigente["id"])["resumen"], "Cambio de otra instancia")
        self.assertIn(self.p["textos"]["bloqueado"], self.vista.banner.texto)

    def test_editar_y_borrar_memoria_reutiliza_editor_sin_llamar_modelo(self):
        self.enviar("Dato recordado")
        self.boton().click()
        self.generar.reset_mock()
        self.vista._editar_memoria()
        self.vista.resumen.clear()
        self.vista._confirmar_edicion()
        self.assertEqual(self.repo.leer(self.vista._datos["id"])["resumen"], "")
        self.generar.assert_not_called()
