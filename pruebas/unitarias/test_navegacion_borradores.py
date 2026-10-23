"""Pruebas unitarias de navegación integrada y memoria temporal de borradores."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
from procesos_ia.dominio.evaluaciones import DefinicionResultado
from procesos_ia.dominio.modelos import ConfiguracionTrabajo
from procesos_ia.dominio.prompts import PlantillaPrompt
from procesos_ia.infraestructura.ollama.servicio_inferencia import ServicioInferenciaOllama
from procesos_ia.infraestructura.prompts.repositorio_md import RepositorioPromptsMd
from procesos_ia.interfaz.borradores import GestorBorradores
from procesos_ia.interfaz.dialogo_preparacion import DialogoPrepararTrabajo
from procesos_ia.interfaz.dialogo_prompt import DialogoGestionPrompts
from procesos_ia.interfaz.ventana_principal import VentanaPrincipal


class PruebaNavegacionBorradores(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.raiz = Path(self.temp_dir.name)
        self.archivo_csv = self.raiz / "datos.csv"
        self.archivo_csv.write_text("comentario,categoria\nHola,A\n", encoding="utf-8")

        self.resultado = DefinicionResultado(
            "sentimiento", "Analizar sentimiento", ("datos",), "texto", ("positivo", "negativo"),
        )
        self.plantilla = PlantillaPrompt(
            "p1", "Plantilla Prueba", "Evaluar sentimiento", "clasificacion", "Prompt texto",
            resultados=(self.resultado,),
        )
        self.gestor_borradores = GestorBorradores()

    def test_borrador_prompts_se_conserva_y_se_restaura(self) -> None:
        repo = RepositorioPromptsMd(self.raiz / "prompts")
        servicio = ServicioCatalogoPrompts(repo, MagicMock())
        vista = DialogoGestionPrompts(servicio, "simulado", self.gestor_borradores)
        vista._crear_nuevo()

        vista.input_titulo.setText("Título en progreso")
        vista.input_categoria.setText("mi_categoria")
        vista.input_descripcion.setText("Nota sin guardar")
        vista.texto_contenido.setPlainText("Mi borrador de prompt extenso")

        # Salir o volver: guarda borrador
        vista._al_volver()
        self.assertTrue(self.gestor_borradores.tiene_borrador_prompts())

        # Nueva sesión con el mismo gestor
        vista2 = DialogoGestionPrompts(servicio, "simulado", self.gestor_borradores)
        self.assertTrue(vista2.restaurar_borrador_si_existe())
        self.assertEqual(vista2.input_titulo.text(), "Título en progreso")
        self.assertEqual(vista2.input_categoria.text(), "mi_categoria")
        self.assertEqual(vista2.texto_contenido.toPlainText(), "Mi borrador de prompt extenso")

        # Limpiar borrador desde botón
        vista2.limpiar_borrador()
        self.assertFalse(self.gestor_borradores.tiene_borrador_prompts())
        self.assertEqual(vista2.input_titulo.text(), "Nueva Plantilla")

    def test_borrador_preparacion_restaura_vinculos_y_permite_limpiar(self) -> None:
        config = ConfiguracionTrabajo(
            self.archivo_csv, self.raiz / "salida", "simulado", 2, 1000, 512, 0.0, 10.0,
            ("comentario",), self.plantilla.contenido, "csv", ("sentimiento_ia",),
        )
        inferencia = MagicMock(spec=ServicioInferenciaOllama)
        vista = DialogoPrepararTrabajo(
            config, self.plantilla, ("comentario", "categoria"), inferencia, self.gestor_borradores,
        )

        vista.salidas["sentimiento"].setText("columna_personalizada")
        vista._al_volver()
        self.assertTrue(self.gestor_borradores.tiene_borrador_preparacion())

        vista2 = DialogoPrepararTrabajo(
            config, self.plantilla, ("comentario", "categoria"), inferencia, self.gestor_borradores,
        )
        self.assertTrue(vista2.restaurar_borrador_si_existe())
        self.assertEqual(vista2.salidas["sentimiento"].text(), "columna_personalizada")

        vista2.limpiar_borrador()
        self.assertFalse(self.gestor_borradores.tiene_borrador_preparacion())
        self.assertEqual(vista2.salidas["sentimiento"].text(), "sentimiento_ia")

    def test_navegacion_en_ventana_principal_sin_ventanas_flotantes(self) -> None:
        repo = RepositorioPromptsMd(self.raiz / "prompts")
        servicio = ServicioCatalogoPrompts(repo, MagicMock())
        ventana = VentanaPrincipal(
            coordinador=MagicMock(),
            cliente_ollama=MagicMock(),
            servicio_prompts=servicio,
            directorio_base=self.raiz,
        )
        self.assertEqual(ventana.pila_vistas.currentWidget(), ventana.vista_principal)

        # Abrir gestión de prompts conmuta la vista embebida
        ventana._abrir_dialogo_prompts()
        self.assertNotEqual(ventana.pila_vistas.currentWidget(), ventana.vista_principal)
        self.assertEqual(ventana.pila_vistas.currentWidget(), ventana._vista_prompts)

        # Volver regresa a la vista principal
        ventana._volver_a_principal()
        self.assertEqual(ventana.pila_vistas.currentWidget(), ventana.vista_principal)
