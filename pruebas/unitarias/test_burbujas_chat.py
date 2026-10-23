"""Regresión de autores recortados en respuestas cortas y burbujas estrechas."""

import os
from pathlib import Path
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtGui import QFontDatabase, QFontMetricsF
from PySide6.QtWidgets import QApplication, QLabel

from procesos_ia.infraestructura.ollama.parametros_chat import cargar_parametros_chat
from procesos_ia.interfaz.mensajes_chat import PanelMensajes, TextoMensaje
from procesos_ia.interfaz.tema import construir_hoja_estilos


class PruebaBurbujasChat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if os.environ.get("WINDIR"):
            for nombre in ("segoeui.ttf", "segoeuib.ttf"):
                ruta = Path(os.environ["WINDIR"]) / "Fonts" / nombre
                if ruta.is_file():
                    QFontDatabase.addApplicationFont(str(ruta))

    def setUp(self):
        self.parametros = cargar_parametros_chat()
        self.panel = PanelMensajes(self.parametros)
        self.panel.setStyleSheet(construir_hoja_estilos() + self.parametros["estilo"]["hoja"])
        self.addCleanup(self.panel.deleteLater)

    def mostrar(self, texto, modelo="qwen3:4b-instruct", ancho=1000, estado="completo"):
        self.panel.resize(ancho, 450)
        self.panel.mostrar([{"id": "prueba", "rol": "assistant", "texto": texto,
                             "estado": estado}], modelo)
        self.panel.show()
        self.procesar()
        return self.panel._burbujas[0][0]

    def procesar(self):
        for _ in range(12):
            self.app.processEvents()

    def comprobar_texto_visible(self, burbuja):
        for etiqueta in burbuja.findChildren(QLabel):
            self.assertGreaterEqual(etiqueta.height(), etiqueta.heightForWidth(etiqueta.width()))
        cuerpo = burbuja.findChild(TextoMensaje)
        self.assertGreaterEqual(cuerpo.viewport().height(), cuerpo.document().size().height())
        self.assertEqual(cuerpo.horizontalScrollBar().maximum(), 0)

    def test_respuesta_corta_reserva_ancho_para_el_autor_con_estilo_aplicado(self):
        burbuja = self.mostrar("2 + 6 = 8.")
        autor = burbuja.findChild(QLabel, "autor_mensaje")
        self.assertGreaterEqual(autor.width(), QFontMetricsF(autor.font()).horizontalAdvance(autor.text()))
        self.comprobar_texto_visible(burbuja)

    def test_modelo_largo_ajusta_altura_al_reducir_y_ampliar_ancho(self):
        burbuja = self.mostrar("8.", "qwen3:4b-instruct-con-un-nombre-de-modelo-muy-largo")
        for ancho in (320, 700, 1000, 240, 1000):
            self.panel.resize(ancho, 450)
            self.procesar()
            self.comprobar_texto_visible(burbuja)

    def test_pendiente_y_texto_multilinea_se_ven_completos(self):
        burbuja = self.mostrar("Primera línea\nSegunda línea\nÚltima línea", ancho=320, estado="pendiente")
        self.comprobar_texto_visible(burbuja)

    def test_cambio_de_fuente_del_cuerpo_recalcula_altura(self):
        burbuja = self.mostrar("Respuesta de varias palabras que debe poder ajustarse al cambiar la fuente.", ancho=320)
        cuerpo = burbuja.findChild(TextoMensaje)
        fuente = cuerpo.font()
        fuente.setPointSizeF(fuente.pointSizeF() * 1.5)
        cuerpo.setFont(fuente)
        self.procesar()
        self.comprobar_texto_visible(burbuja)
