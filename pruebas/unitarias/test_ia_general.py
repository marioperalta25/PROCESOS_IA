"""Pruebas unitarias para el modulo de IA General (Google Lens y Modo IA)."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from PySide6.QtWidgets import QApplication

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.servicio_ia_general import ServicioIAGeneral
from procesos_ia.dominio.ficha_negocio import FichaNegocioLens
from procesos_ia.infraestructura.web.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.manipulador_dom_lens import (
    parsear_sintesis_negocio,
)
from procesos_ia.infraestructura.web.manipulador_dom_modo_ia import (
    extraer_datos_estructurados_modo_ia,
)
from procesos_ia.interfaz.vista_ia_general import VistaIAGeneral
from procesos_ia.interfaz.vista_motores import VistaConfiguracionMotores

_APP = QApplication.instance() or QApplication([])


class TestIAGeneralDominio(unittest.TestCase):
    """Verifica las entidades de dominio y el parseo de fichas de negocio."""

    def test_parsear_ejemplo_documento_auner_fuentes(self) -> None:
        texto = (
            "La tarjeta de presentación pertenece a Auner Fuentes, propietario de "
            "Moisés Luxury Remodeling, un negocio de remodelación y construcción en Tampa, Florida."
        )
        enlaces = ["https://www.thumbtack.com/fl/tampa", "https://www.facebook.com/moises"]
        ficha = parsear_sintesis_negocio(texto, enlaces, id_registro="tarjeta_1")

        self.assertEqual(ficha.id_registro, "tarjeta_1")
        self.assertEqual(ficha.propietario, "Auner Fuentes")
        self.assertEqual(ficha.negocio, "Moises Luxury Remodeling")
        self.assertIn("remodelacion y construccion", ficha.categoria)
        self.assertIn("Tampa, Florida", ficha.ubicacion)
        self.assertEqual(len(ficha.enlaces), 2)

    def test_parsear_ejemplo_joseph_tapia(self) -> None:
        texto = "Alegre Roofing & Construction Additional phone 505 316 1088 Additional contact name Joseph Tapia"
        ficha = parsear_sintesis_negocio(texto, id_registro="roofing_1")

        self.assertEqual(ficha.propietario, "Joseph Tapia")
        self.assertIn("505 316 1088", ficha.telefono)

    def test_parsear_ejemplo_jesus_lopez(self) -> None:
        texto = "Lopez Landscaping And Masonry Owner Jesus Lopez 602 579 4177 Service Tech Julian Argot 602 354 6803"
        ficha = parsear_sintesis_negocio(texto, id_registro="lopez_1")

        self.assertEqual(ficha.propietario, "Jesus Lopez")
        self.assertIn("602 579 4177", ficha.telefono)

    def test_parsear_idiomas(self) -> None:
        texto = "Star Roofing & Construction\nPropietario: Ulises Garcia\nIdiomas: Hablamos Español / We speak English"
        ficha = parsear_sintesis_negocio(texto, id_registro="star_1")
        self.assertEqual(ficha.propietario, "Ulises Garcia")
        self.assertIn("Espanol", ficha.idiomas)

    def test_ficha_a_diccionario_y_normalizacion(self) -> None:
        ficha = FichaNegocioLens(
            id_registro="1",
            propietario="Iñigo Peña",
            negocio="Diseño & Baños",
            categoria="Construcción",
            enlaces=["https://sitio1.com", "https://sitio2.com"],
        )
        datos = ficha.a_diccionario(normalizado=True)
        self.assertEqual(datos["propietario"], "Inigo Pena")
        self.assertEqual(datos["negocio"], "Diseno & Banos")
        self.assertEqual(datos["categoria"], "Construccion")
        self.assertIn("sitio1.com ; https://sitio2.com", datos["enlaces_str"])


class TestModoIAExtraccion(unittest.TestCase):
    """Verifica la extraccion y saneamiento de respuestas JSON en Modo IA."""

    def test_extraer_json_valido(self) -> None:
        texto = '```json\n{"resultados": [{"id": 1, "calificacion": "A"}]}\n```'
        res = extraer_datos_estructurados_modo_ia(texto)
        self.assertIsInstance(res, dict)
        self.assertIn("resultados", res)
        self.assertEqual(res["resultados"][0]["calificacion"], "A")

    def test_extraer_json_con_texto_circundante(self) -> None:
        texto = 'El analisis determina:\n{"id": 2, "nombre": "Carlos"}\nFin de evaluacion.'
        res = extraer_datos_estructurados_modo_ia(texto)
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get("id"), 2)


class TestServicioIAGeneralGuardado(unittest.TestCase):
    """Verifica el guardado en rutas centralizadas sin crear perfiles nuevos."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.enrutador = EnrutadorSalidas(Path(self.temp_dir.name))
        self.config_web = ConfiguracionWeb()
        self.servicio = ServicioIAGeneral(
            gestor_sesion=None,
            configuracion_web=self.config_web,
            enrutador=self.enrutador,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_guardar_fichas_csv(self) -> None:
        fichas = [
            FichaNegocioLens(id_registro="1", propietario="Juan", negocio="Taller"),
            FichaNegocioLens(id_registro="2", propietario="Pedro", negocio="Plomeria"),
        ]
        destino = self.enrutador.extracciones / "prueba_fichas.csv"
        self.enrutador.asegurar_directorios()
        self.servicio._guardar_fichas_csv(fichas, destino)

        self.assertTrue(destino.exists())
        contenido = destino.read_text(encoding="utf-8-sig")
        self.assertIn("Juan", contenido)
        self.assertIn("Plomeria", contenido)
        self.assertIn("idiomas", contenido)


class TestInterfazIAGeneral(unittest.TestCase):
    """Verifica la integracion de componentes en VistaConfiguracionMotores y VistaIAGeneral."""

    def test_boton_ia_general_en_vista_motores(self) -> None:
        vista = VistaConfiguracionMotores()
        self.assertTrue(hasattr(vista, "btn_ia_general"))
        self.assertTrue(hasattr(vista, "ia_general_solicitado"))

        recibido = []
        vista.ia_general_solicitado.connect(lambda: recibido.append(True))
        vista.btn_ia_general.click()
        self.assertTrue(len(recibido) > 0)

    def test_inicializacion_vista_ia_general(self) -> None:
        vista = VistaIAGeneral()
        self.assertEqual(vista.combo_flujo.count(), 4)
        self.assertTrue(hasattr(vista, "btn_ejecutar"))
        self.assertTrue(hasattr(vista, "btn_cancelar"))
        self.assertTrue(hasattr(vista, "tabla"))
        self.assertTrue(hasattr(vista, "consola"))
        self.assertTrue(hasattr(vista, "panel_archivo"))

    def test_consola_ia_general(self) -> None:
        from procesos_ia.interfaz.componentes.consola_ia_general import ConsolaIAGeneral
        consola = ConsolaIAGeneral()
        consola.agregar_log("[INFO] Prueba de lote enviado")
        self.assertIn("Prueba de lote enviado", consola.texto_log.toPlainText())
        consola.limpiar()
        self.assertIn("Bitácora reiniciada", consola.texto_log.toPlainText())

    def test_panel_archivo_general(self) -> None:
        from procesos_ia.interfaz.componentes.panel_archivo_general import PanelArchivoGeneral
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("id,nombre,imagen_url\n1,Carlos,https://img.jpg\n")
            ruta = Path(f.name)

        try:
            panel = PanelArchivoGeneral()
            panel.cargar_archivo(ruta)
            cols = panel.obtener_columnas_seleccionadas()
            self.assertIn("nombre", cols)
            self.assertIn("imagen_url", cols)
            self.assertEqual(panel.combo_columna_img.count(), 4)  # (Ninguna) + id + nombre + imagen_url
        finally:
            ruta.unlink(missing_ok=True)

    def test_plantillas_ia_web_sembrado_y_delimitador(self) -> None:
        from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
        from procesos_ia.aplicacion.prompts_ia_web import asegurar_plantillas_ia_web, CATEGORIA_IA_WEB
        from procesos_ia.infraestructura.prompts.repositorio_md import RepositorioPromptsMd

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = RepositorioPromptsMd(Path(tmp_dir))
            servicio = ServicioCatalogoPrompts(repo)
            plantillas = asegurar_plantillas_ia_web(servicio)

            self.assertGreaterEqual(len(plantillas), 3)
            for p in plantillas:
                self.assertEqual(p.categoria, CATEGORIA_IA_WEB)
                self.assertIn(" | ", p.contenido)

    def test_seleccion_plantilla_en_vista_ia_general(self) -> None:
        vista = VistaIAGeneral()
        self.assertGreater(vista.combo_plantillas.count(), 1)

        # Seleccionar la primera plantilla real (indice 1)
        vista.combo_plantillas.setCurrentIndex(1)
        texto = vista.txt_instrucciones.toPlainText()
        self.assertTrue(len(texto) > 0)
        self.assertIn(" | ", texto)

    def test_boton_plantillas_web_en_vista_motores(self) -> None:
        vista = VistaConfiguracionMotores()
        self.assertTrue(hasattr(vista, "btn_plantillas_ia_web"))
        recibido = []
        vista.plantillas_web_solicitadas.connect(lambda: recibido.append(True))
        vista.btn_plantillas_ia_web.click()
        self.assertEqual(len(recibido), 1)

    def test_boton_insertar_delimitador_en_dialogo_prompts(self) -> None:
        from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
        from procesos_ia.infraestructura.prompts.repositorio_md import RepositorioPromptsMd
        from procesos_ia.interfaz.dialogo_prompt import DialogoGestionPrompts

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = RepositorioPromptsMd(Path(tmp_dir))
            servicio = ServicioCatalogoPrompts(repo)
            dialogo = DialogoGestionPrompts(servicio, modelo_activo="test")
            self.assertTrue(hasattr(dialogo, "btn_delimitador"))
            dialogo.btn_delimitador.click()
            self.assertIn(" | ", dialogo.texto_contenido.toPlainText())

    def test_contenedor_pantalla_responsiva(self) -> None:
        from PySide6.QtWidgets import QLabel
        from procesos_ia.interfaz.componentes.contenedor_responsivo import ContenedorPantallaResponsiva
        from procesos_ia.interfaz.responsivo import ModoPantalla

        contenedor = ContenedorPantallaResponsiva()
        lbl = QLabel("Test")
        contenedor.agregar_widget(lbl)
        self.assertIsNotNone(contenedor.scroll_area)
        self.assertEqual(contenedor.modo_actual, ModoPantalla.ESTANDAR)

    def test_editor_texto_expandible(self) -> None:
        from procesos_ia.interfaz.componentes.editor_texto_expandible import EditorTextoExpandible

        editor = EditorTextoExpandible(altura_inicial=100)
        editor.setPlainText("Linea 1\nLinea 2\nLinea 3")
        self.assertEqual(editor.toPlainText(), "Linea 1\nLinea 2\nLinea 3")

        # Probar expansion hacia abajo
        altura_antes = editor._altura_actual
        editor._expandir_altura()
        self.assertGreater(editor._altura_actual, altura_antes)

        # Probar contraccion
        editor._contraer_altura()
        self.assertEqual(editor._altura_actual, altura_antes)

    def test_consola_ia_general_expansion(self) -> None:
        from procesos_ia.interfaz.componentes.consola_ia_general import ConsolaIAGeneral

        consola = ConsolaIAGeneral()
        alt_inicial = consola._altura_actual
        consola._expandir_altura()
        self.assertGreater(consola._altura_actual, alt_inicial)
        consola._contraer_altura()
        self.assertEqual(consola._altura_actual, alt_inicial)

    def test_tirador_redimension_vertical(self) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QListWidget, QVBoxLayout, QWidget
        from procesos_ia.interfaz.componentes.tirador_ajustable import TiradorRedimensionVertical, adjuntar_tirador_redimension

        w = QWidget(); lay = QVBoxLayout(w)
        lista = QListWidget(); lista.setFixedHeight(100); lay.addWidget(lista)
        tirador = adjuntar_tirador_redimension(lay, lista, altura_min=80, altura_max=300)

        self.assertEqual(tirador.cursor().shape(), Qt.CursorShape.SizeVerCursor)
        self.assertEqual(tirador.widget_objetivo, lista)
        self.assertEqual(tirador.altura_min, 80)
        self.assertEqual(tirador.altura_max, 300)




