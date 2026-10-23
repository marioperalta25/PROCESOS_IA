"""Fragmentos visibles, conservación de widgets y aislamiento entre chats."""

import os
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QThread, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from procesos_ia.aplicacion.conversacion import ServicioConversacion
from procesos_ia.infraestructura.ollama.parametros_chat import cargar_parametros_chat
from procesos_ia.infraestructura.persistencia.repositorio_chat import RepositorioChat
from procesos_ia.interfaz.mensajes_chat import TextoMensaje
from procesos_ia.interfaz.vista_chat import VistaChat


class PruebaProgresoChatInterfaz(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.p = cargar_parametros_chat()
        self.p["limites"]["progreso_intervalo_segundos"] = 0
        self.repo = RepositorioChat(Path(temporal.name), self.p)
        self.generar = MagicMock(return_value="Confirmado")
        servicio = ServicioConversacion(self.repo, self.generar, self.p)
        self.vista = VistaChat(servicio, self.p, lambda: ("simulado", 2048, 0.1), lambda: False)
        self.addCleanup(self.vista.deleteLater)

    def esperar(self, condicion):
        for _ in range(300):
            self.app.processEvents()
            if condicion():
                return
            QTest.qWait(10)
        self.fail("La respuesta no avanzó")

    def enviar(self, texto):
        self.vista.entrada.setPlainText(texto)
        self.vista._enviar()

    def test_fragmentos_visibles_sin_recrear_burbujas_y_confirmacion_final(self):
        hilos = []
        actualizar = self.vista.transcripcion.actualizar_ultimo
        def observar(texto):
            hilos.append(QThread.currentThread())
            actualizar(texto)
        self.vista.transcripcion.actualizar_ultimo = observar
        continuar, terminar = Event(), Event()
        self.addCleanup(terminar.set)
        self.addCleanup(continuar.set)
        def generar(*args, **opciones):
            opciones["al_fragmento"]("Hola")
            continuar.wait(3)
            opciones["al_fragmento"](" mundo")
            terminar.wait(3)
            return "Hola mundo"
        self.generar.side_effect = generar
        self.enviar("Consulta")
        self.esperar(lambda: "Hola" in self.vista.transcripcion.toPlainText())
        identidad = self.vista._datos["id"]
        self.assertEqual(len(self.repo.leer(identidad)["mensajes"]), 1)
        cuerpo = self.vista.transcripcion._burbujas[-1][0].findChild(TextoMensaje)
        continuar.set()
        self.esperar(lambda: "Hola mundo" in self.vista.transcripcion.toPlainText())
        self.assertIs(cuerpo, self.vista.transcripcion._burbujas[-1][0].findChild(TextoMensaje))
        self.assertEqual(hilos, [self.app.thread()])
        terminar.set()
        self.esperar(lambda: self.vista._hilo is None)
        self.assertEqual(self.repo.leer(identidad)["mensajes"][-1]["texto"], "Hola mundo")
        self.assertEqual(len(self.vista._datos["mensajes"]), 2)

    def test_cambiar_de_chat_y_volver_no_cruza_fragmentos_y_cancelar_los_descarta(self):
        self.enviar("Chat A")
        self.esperar(lambda: self.vista._hilo is None)
        identidad_a = self.vista._datos["id"]
        self.vista._nuevo()
        self.enviar("Chat B")
        self.esperar(lambda: self.vista._hilo is None)
        identidad_b = self.vista._datos["id"]
        def seleccionar(identidad):
            fila = next(i for i in range(self.vista.lista.count())
                        if self.vista.lista.item(i).data(Qt.ItemDataRole.UserRole) == identidad)
            self.vista.lista.setCurrentRow(fila)
        seleccionar(identidad_a)
        terminar = Event()
        self.addCleanup(terminar.set)
        def generar(*args, **opciones):
            opciones["al_fragmento"]("Parcial exclusivo A")
            terminar.wait(3)
            return "No confirmar"
        self.generar.side_effect = generar
        self.enviar("Continúa A")
        self.esperar(lambda: "Parcial exclusivo A" in self.vista.transcripcion.toPlainText())
        seleccionar(identidad_b)
        self.assertNotIn("Parcial exclusivo A", self.vista.transcripcion.toPlainText())
        seleccionar(identidad_a)
        self.assertIn("Parcial exclusivo A", self.vista.transcripcion.toPlainText())
        self.assertEqual(self.vista.transcripcion.toPlainText().count("Continúa A"), 1)
        self.vista._enviar()
        terminar.set()
        self.esperar(lambda: self.vista._hilo is None)
        self.assertNotIn("Parcial exclusivo A", self.vista.transcripcion.toPlainText())
        self.assertEqual(self.repo.leer(identidad_a)["mensajes"][-1]["estado"], "cancelado")
