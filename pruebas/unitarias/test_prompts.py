"""Pruebas unitarias para el repositorio de prompts (.md) y el refinador asistido."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.dominio.prompts import (
    PeticionRefinamiento,
    PlantillaPrompt,
    ResultadoRefinamiento,
)
from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.prompts.refinador_ollama import (
    RefinadorPromptOllama,
)
from procesos_ia.infraestructura.prompts.repositorio_md import (
    RepositorioPromptsMd,
)


class PruebaCatalogoPrompts(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temp_dir.name)
        self.repo = RepositorioPromptsMd(self.raiz)
        self.servicio = ServicioCatalogoPrompts(repositorio=self.repo)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_guardar_y_recuperar_plantilla_md(self) -> None:
        plantilla = self.servicio.crear_plantilla(
            titulo="Clasificador de Mensajes",
            contenido="Eres un clasificador experto...",
            categoria="Soporte",
            descripcion="Clasifica quejas y sugerencias",
            columnas_requeridas=("mensaje",),
            columnas_salida=("categoria", "urgencia"),
        )

        self.assertEqual(plantilla.identificador, "clasificador_de_mensajes")

        # Verificar archivo físico .md
        ruta_md = self.raiz / "clasificador_de_mensajes.md"
        self.assertTrue(ruta_md.is_file())
        texto = ruta_md.read_text(encoding="utf-8")
        self.assertIn("titulo: Clasificador de Mensajes", texto)
        self.assertIn("categoria: Soporte", texto)
        self.assertIn("Eres un clasificador experto...", texto)

        # Recuperar desde disco
        recuperada = self.servicio.obtener_plantilla("clasificador_de_mensajes")
        self.assertIsNotNone(recuperada)
        assert recuperada is not None
        self.assertEqual(recuperada.titulo, "Clasificador de Mensajes")
        self.assertEqual(recuperada.categoria, "Soporte")
        self.assertEqual(recuperada.columnas_salida, ("categoria", "urgencia"))
        self.assertEqual(recuperada.contenido, "Eres un clasificador experto...")

    def test_listar_y_filtrar_por_categoria(self) -> None:
        self.servicio.crear_plantilla(
            titulo="P1", contenido="c1", categoria="Soporte"
        )
        self.servicio.crear_plantilla(
            titulo="P2", contenido="c2", categoria="Ventas"
        )
        self.servicio.crear_plantilla(
            titulo="P3", contenido="c3", categoria="Soporte"
        )

        todas = self.servicio.listar_plantillas()
        self.assertEqual(len(todas), 3)

        soporte = self.servicio.listar_plantillas(categoria="Soporte")
        self.assertEqual(len(soporte), 2)

        ventas = self.servicio.listar_plantillas(categoria="Ventas")
        self.assertEqual(len(ventas), 1)

    def test_eliminar_plantilla(self) -> None:
        self.servicio.crear_plantilla(titulo="Temporal", contenido="temp")
        self.assertTrue(self.servicio.eliminar_plantilla("temporal"))
        self.assertIsNone(self.servicio.obtener_plantilla("temporal"))

    def test_validacion_titulo_o_contenido_vacio(self) -> None:
        with self.assertRaises(ErrorProcesamiento):
            self.servicio.crear_plantilla(titulo="", contenido="algo")

        with self.assertRaises(ErrorProcesamiento):
            self.servicio.crear_plantilla(titulo="algo", contenido="   ")

    def test_refinador_ollama_exitoso(self) -> None:
        cliente_mock = MagicMock(spec=ClienteHttpOllama)
        cliente_mock.generar_estructurado.return_value = {
            "prompt_refinado": "Eres un asistente de soporte. Responde en JSON con {categoria}.",
            "columnas_salida": ["categoria", "prioridad"],
            "explicacion": "Se agregaron instrucciones de salida estricta en JSON.",
        }

        refinador = RefinadorPromptOllama(cliente_http=cliente_mock)
        servicio_con_refinador = ServicioCatalogoPrompts(
            repositorio=self.repo, motor_refinamiento=refinador
        )

        peticion = PeticionRefinamiento(
            idea_usuario="Quiero clasificar los mensajes que llegan de clientes",
            columnas_entrada=("mensaje",),
            ejemplo_fila={"mensaje": "No me funciona el acceso"},
        )

        res = servicio_con_refinador.refinar_idea(peticion, nombre_modelo="qwen2.5:1.5b")
        self.assertIn("asistente de soporte", res.prompt_refinado)
        self.assertEqual(res.columnas_salida_sugeridas, ("categoria", "prioridad"))
        self.assertIn("JSON", res.explicacion_resumen)


if __name__ == "__main__":
    unittest.main()
