"""Integración nativa, navegación, adaptación y cierre del chat."""

import os
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from procesos_ia.aplicacion.conversacion import ServicioConversacion
from procesos_ia.infraestructura.ollama.parametros_chat import cargar_parametros_chat
from procesos_ia.infraestructura.persistencia.repositorio_chat import RepositorioChat
from procesos_ia.interfaz.vista_chat import VistaChat
from procesos_ia.interfaz.ventana_principal import VentanaPrincipal


class PruebaInterfazChat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)
        self.parametros = cargar_parametros_chat()
        self.repo = RepositorioChat(self.raiz / "historial", self.parametros)
        self.generador = MagicMock(return_value="Texto de prueba <sin HTML>")
        servicio = ServicioConversacion(self.repo, self.generador, self.parametros)
        self.vista = VistaChat(servicio, self.parametros, lambda: ("simulado", 4096, 0.1), lambda: False)
        self.addCleanup(self.vista.deleteLater)

    def esperar(self, condicion):
        for _ in range(300):
            self.app.processEvents()
            if condicion():
                return
            QTest.qWait(10)
        self.fail("La tarea no terminó a tiempo")

    def enviar(self, texto):
        self.vista.entrada.setPlainText(texto)
        self.vista._enviar()
        self.esperar(lambda: self.vista._hilo is None)

    def test_envio_historial_renombrado_memoria_y_borrado_integrados(self):
        self.enviar("Consulta de prueba")
        self.assertIn("<sin HTML>", self.vista.transcripcion.toPlainText())
        self.assertEqual(self.vista.lista.count(), 1)
        self.vista._editar_nombre()
        self.vista.nombre.setText("Categorías locales")
        self.vista._confirmar_edicion()
        self.assertEqual(self.vista._datos["titulo"], "Categorías locales")
        self.vista._editar_memoria()
        self.vista.resumen.setPlainText("Preferencia explícita del usuario")
        self.vista._confirmar_edicion()
        self.assertEqual(self.repo.leer(self.vista._datos["id"])["resumen"], "Preferencia explícita del usuario")
        self.vista._pedir_borrado()
        self.vista._confirmar_edicion()
        self.assertEqual(self.repo.listar(), [])
        self.assertEqual(self.vista._datos["mensajes"], [])

    def test_borradores_y_resultados_tardios_no_cruzan_chats(self):
        self.enviar("Chat A")
        identidad_a = self.vista._datos["id"]
        self.vista._nuevo()
        self.enviar("Chat B")
        self.vista.entrada.setPlainText("Borrador B")
        item_a = next(self.vista.lista.item(i) for i in range(self.vista.lista.count())
                      if self.vista.lista.item(i).data(Qt.ItemDataRole.UserRole) == identidad_a)
        self.vista.lista.setCurrentItem(item_a)
        self.assertEqual(self.vista.entrada.toPlainText(), "")
        self.vista.entrada.setPlainText("Borrador A")
        self.vista._al_resultado(self.repo.leer(next(c["id"] for c in self.repo.listar() if c["id"] != identidad_a)), "ok")
        self.assertEqual(self.vista._datos["id"], identidad_a)
        self.assertEqual(self.vista.entrada.toPlainText(), "Borrador A")

    def test_entrada_excesiva_conserva_borrador_y_no_infiere(self):
        self.vista.entrada.setPlainText("Borrador válido")
        self.vista.entrada.setPlainText("á" * self.parametros["limites"]["entrada_bytes"])
        self.assertEqual(self.vista.entrada.toPlainText(), "Borrador válido")
        self.generador.assert_not_called()

    def test_nuevo_chat_conserva_borrador_no_enviado_accesible_sin_archivo(self):
        identidad = self.vista._datos["id"]
        self.vista.entrada.setPlainText("Idea pendiente sin enviar")
        self.vista._nuevo()
        self.assertEqual(self.vista.lista.count(), 1)
        self.assertEqual(self.vista.lista.item(0).data(Qt.ItemDataRole.UserRole), identidad)
        self.assertFalse(self.repo.existe(identidad))
        self.vista.lista.setCurrentRow(0)
        self.assertEqual(self.vista.entrada.toPlainText(), "Idea pendiente sin enviar")

    def test_respuesta_activa_permanece_en_origen_al_cambiar_de_chat(self):
        self.enviar("Chat A")
        identidad_a = self.vista._datos["id"]
        self.vista._nuevo()
        self.enviar("Chat B")
        identidad_b = self.vista._datos["id"]
        fila_a = next(i for i in range(self.vista.lista.count())
                      if self.vista.lista.item(i).data(Qt.ItemDataRole.UserRole) == identidad_a)
        self.vista.lista.setCurrentRow(fila_a)
        iniciado, liberar = Event(), Event()
        def generar(*args, **kwargs):
            iniciado.set()
            liberar.wait(2)
            return "Respuesta exclusiva de A"
        self.generador.side_effect = generar
        self.vista.entrada.setPlainText("Otra pregunta en A")
        self.vista._enviar()
        self.esperar(iniciado.is_set)
        fila_b = next(i for i in range(self.vista.lista.count())
                      if self.vista.lista.item(i).data(Qt.ItemDataRole.UserRole) == identidad_b)
        self.vista.lista.setCurrentRow(fila_b)
        self.vista.entrada.setPlainText("Borrador de B")
        liberar.set()
        self.esperar(lambda: self.vista._hilo is None)
        self.assertEqual(self.vista._datos["id"], identidad_b)
        self.assertNotIn("Respuesta exclusiva de A", self.vista.transcripcion.toPlainText())
        self.assertEqual(self.vista.entrada.toPlainText(), "Borrador de B")
        self.assertEqual(self.repo.leer(identidad_a)["mensajes"][-1]["texto"], "Respuesta exclusiva de A")

    def test_teclado_y_selector_historial_compacto(self):
        from procesos_ia.interfaz.responsivo import ModoPantalla
        self.vista.adaptar_modo(ModoPantalla.COMPACTO)
        self.vista._alternar_historial()
        self.assertTrue(self.vista.panel_conversacion.isHidden())
        self.vista._nuevo()
        self.assertTrue(self.vista.lateral.isHidden())
        self.assertFalse(self.vista.panel_conversacion.isHidden())
        self.vista.entrada.setPlainText("Pregunta")
        QTest.keyClick(self.vista.entrada, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        self.generador.assert_not_called()
        QTest.keyClick(self.vista.entrada, Qt.Key.Key_Return)
        self.esperar(lambda: self.vista._hilo is None)
        self.generador.assert_called_once()

    def test_volver_durante_peticion_espera_y_descarta_respuesta_cancelada(self):
        iniciado, liberar = Event(), Event()
        def generar(*args, **kwargs):
            iniciado.set()
            liberar.wait(2)
            return "Respuesta tardía"
        self.generador.side_effect = generar
        volver = MagicMock()
        self.vista.volver_solicitado.connect(volver)
        self.vista.entrada.setPlainText("Hola")
        self.vista._enviar()
        self.esperar(iniciado.is_set)
        self.vista._volver()
        volver.assert_not_called()
        liberar.set()
        self.esperar(lambda: self.vista._hilo is None)
        volver.assert_called_once()
        self.assertEqual(self.vista._datos["mensajes"][-1]["estado"], "cancelado")

    def test_chat_se_abre_una_vez_en_pila_y_cierre_espera_su_hilo(self):
        with patch.object(VentanaPrincipal, "_actualizar_modelos_segundo_plano"), patch.object(
            QStandardPaths, "writableLocation", return_value=str(self.raiz / "usuario"),
        ):
            ventana = VentanaPrincipal(cliente_ollama=MagicMock(), servicio_prompts=MagicMock(),
                                       directorio_base=self.raiz)
            ventana.resize(750, 650)
            ventana.show()
            self.app.processEvents()
            ventana._navegacion.abrir_chat()
            chat = ventana._navegacion.chat
            ventana._volver_a_principal()
            ventana._navegacion.abrir_chat()
            self.assertIs(ventana.pila_vistas.currentWidget(), chat)
            self.assertEqual(ventana.pila_vistas.count(), 2)
            self.assertEqual(chat.divisor.orientation(), Qt.Orientation.Vertical)
            self.assertTrue(chat.lateral.isHidden())
            self.assertFalse(chat.isWindow())
            liberar, iniciado = Event(), Event()
            def generar(*args, **kwargs):
                iniciado.set()
                liberar.wait(2)
                return "Respuesta"
            chat.servicio._generar = generar
            chat.servicio._preparar_modelo = None
            chat._opciones = lambda: ("simulado", 4096, 0.1)
            chat._selector._catalogo = lambda: ["simulado"]
            chat._selector.preparar_nuevo()
            chat._pintar()
            chat.entrada.setPlainText("Una pregunta")
            chat._enviar()
            self.esperar(iniciado.is_set)
            evento = QCloseEvent()
            ventana.closeEvent(evento)
            self.assertFalse(evento.isAccepted())
            self.assertTrue(ventana._cierre.pendiente)
            liberar.set()
            self.esperar(lambda: chat._hilo is None)
            self.esperar(lambda: not ventana.isVisible())
            ventana.deleteLater()
