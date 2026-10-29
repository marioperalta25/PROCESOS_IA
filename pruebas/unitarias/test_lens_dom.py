"""Pruebas unitarias para manipulacion DOM, selectores y extraccion de Google Lens."""

from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock

from procesos_ia.dominio.ia_web.parseador_ficha_lens import parsear_sintesis_negocio
from procesos_ia.infraestructura.web.visual_1a1.manipulador_dom_lens import (
    abrir_modal_lens,
    cargar_archivo_en_lens,
    cargar_url_en_lens,
    esperar_vision_general_ia,
    extraer_enlaces_relacionados,
)
from procesos_ia.infraestructura.web.visual_1a1.selectores_lens import SELECTORES_LENS


class TestManipuladorDOMLens(unittest.IsolatedAsyncioTestCase):
    """Verifica la extraccion estructurada y metodos DOM de Google Lens."""

    def test_parsear_ficha_estructurada_google_lens(self) -> None:
        texto_lens = (
            "Visión general creada por IA\n"
            "Compañía: Star 2024 Roofing\n"
            "Licencia: #1145136\n"
            "Representante: Ulises (Ejecutivo de Ventas)\n"
            "Teléfono: (949) 279-2125\n"
            "Correo electrónico: Ulisesym45@gmail.com\n"
            "Ubicación referencial del negocio: Baldwin Park, Riverside y áreas cercanas"
        )
        enlaces = ["https://www.facebook.com/star2024roofing", "https://starroofing.com"]
        ficha = parsear_sintesis_negocio(
            texto=texto_lens,
            enlaces=enlaces,
            id_registro="ficha_roofing_1",
            fuente_imagen="techo_ejemplo.jpg",
        )

        self.assertEqual(ficha.id_registro, "ficha_roofing_1")
        self.assertEqual(ficha.negocio, "Star 2024 Roofing")
        self.assertEqual(ficha.licencia, "#1145136")
        self.assertEqual(ficha.propietario, "Ulises (Ejecutivo de Ventas)")
        self.assertEqual(ficha.telefono, "(949) 279-2125")
        self.assertEqual(ficha.correo_electronico, "Ulisesym45@gmail.com")
        self.assertIn("Baldwin Park, Riverside", ficha.ubicacion)
        self.assertEqual(len(ficha.enlaces), 2)

    def test_conservacion_selectores_lens(self) -> None:
        claves_esperadas = [
            "boton_apertura",
            "disparador_subida",
            "zonas_arrastre",
            "campo_url",
            "boton_buscar_url",
            "contenedor_ia",
            "enlaces_relacionados",
        ]
        for clave in claves_esperadas:
            self.assertIn(clave, SELECTORES_LENS)
            self.assertIsInstance(SELECTORES_LENS[clave], list)
            self.assertGreater(len(SELECTORES_LENS[clave]), 0)

        # Verificar selectores especificos provistos por el usuario
        self.assertIn(".n6owBd", SELECTORES_LENS["contenedor_ia"])
        self.assertIn(".mZJni.Dn7Fzd", SELECTORES_LENS["contenedor_ia"])
        self.assertIn("span[jsname='tAPGc']", SELECTORES_LENS["disparador_subida"])
        self.assertIn("div[jsname='WKe3se']", SELECTORES_LENS["zonas_arrastre"])
        self.assertIn("div[jsname='QdEQIc']", SELECTORES_LENS["zonas_arrastre"])

    async def test_abrir_modal_lens(self) -> None:
        elem_mock = MagicMock()
        elem_mock.click = AsyncMock()

        pestana_mock = MagicMock()
        pestana_mock.select = AsyncMock(return_value=elem_mock)

        exito = await abrir_modal_lens(pestana_mock)
        self.assertTrue(exito)
        pestana_mock.select.assert_called()
        elem_mock.click.assert_called_once()

    async def test_cargar_archivo_en_lens_con_fallback_js(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
            ruta_img = Path(f.name)

        try:
            pestana_mock = MagicMock()
            pestana_mock.send = AsyncMock(side_effect=Exception("CDP interceptor no soportado"))
            pestana_mock.add_handler = MagicMock()
            pestana_mock.remove_handler = MagicMock()
            pestana_mock.select = AsyncMock(return_value=None)
            pestana_mock.evaluate = AsyncMock(return_value="DROP_OK")

            exito = await cargar_archivo_en_lens(pestana_mock, ruta_img)
            self.assertTrue(exito)
            pestana_mock.evaluate.assert_called()
        finally:
            ruta_img.unlink(missing_ok=True)

    async def test_cargar_archivo_inexistente_retorna_false(self) -> None:
        pestana_mock = MagicMock()
        exito = await cargar_archivo_en_lens(pestana_mock, Path("ruta_inexistente_xyz.png"))
        self.assertFalse(exito)

    async def test_cargar_url_en_lens(self) -> None:
        input_mock = MagicMock()
        input_mock.send_keys = AsyncMock()
        btn_mock = MagicMock()
        btn_mock.click = AsyncMock()

        async def _select_side_effect(selector: str, timeout: float = 2.0) -> Any:
            if "input" in selector:
                return input_mock
            return btn_mock

        pestana_mock = MagicMock()
        pestana_mock.select = AsyncMock(side_effect=_select_side_effect)

        exito = await cargar_url_en_lens(pestana_mock, "https://imagenes.com/foto.jpg")
        self.assertTrue(exito)
        input_mock.send_keys.assert_called_with("https://imagenes.com/foto.jpg")
        btn_mock.click.assert_called_once()

    async def test_esperar_vision_general_ia_exitoso(self) -> None:
        elem_mock = MagicMock()
        elem_mock.text = "Respuesta de Vision General con suficiente longitud para ser valida."

        async def _mock_select(sel: str, timeout: float = 1.0) -> Any:
            return elem_mock

        pestana_mock = MagicMock()
        pestana_mock.select = AsyncMock(side_effect=_mock_select)
        pestana_mock.evaluate = AsyncMock(return_value={"tipo": "EXITOSO", "texto": elem_mock.text})

        texto, estado = await esperar_vision_general_ia(pestana_mock, timeout_segundos=4)
        self.assertEqual(estado, "EXITOSO")
        self.assertIn("Respuesta de Vision General", texto)

    async def test_esperar_vision_general_ia_sin_vision(self) -> None:
        pestana_mock = MagicMock()
        pestana_mock.select = AsyncMock(return_value=None)
        pestana_mock.evaluate = AsyncMock(return_value={"tipo": "SIN_VISION_GENERAL", "texto": "No hay visión general disponible."})

        texto, estado = await esperar_vision_general_ia(pestana_mock, timeout_segundos=2)
        self.assertEqual(estado, "SIN_VISION_GENERAL")
        self.assertIn("No hay visión general", texto)

    async def test_esperar_vision_general_ia_error_subida(self) -> None:
        pestana_mock = MagicMock()
        pestana_mock.select = AsyncMock(return_value=None)
        pestana_mock.evaluate = AsyncMock(return_value={"tipo": "ERROR_SUBIDA", "texto": "No se pudo subir la imagen."})

        texto, estado = await esperar_vision_general_ia(pestana_mock, timeout_segundos=2)
        self.assertEqual(estado, "ERROR_SUBIDA")
        self.assertIn("No se pudo subir la imagen", texto)

    async def test_extraer_enlaces_relacionados(self) -> None:
        link_mock = MagicMock()
        link_mock.attrs = {"href": "https://fuente-externa.com/perfil"}

        pestana_mock = MagicMock()
        pestana_mock.select_all = AsyncMock(return_value=[link_mock])

        enlaces = await extraer_enlaces_relacionados(pestana_mock)
        self.assertEqual(len(enlaces), 1)
        self.assertEqual(enlaces[0], "https://fuente-externa.com/perfil")

    def test_parsear_ficha_con_bs4_y_multiples_telefonos(self) -> None:
        html = """
        <div class="n6owBd">
          <h2>Visión general creada por IA</h2>
          <div class="awi2gc"><p>La tarjeta de presentación pertenece a la empresa de remodelación Remodeling, cuyo propietario es Auner Fuentes.</p></div>
          <ul>
            <li>Sitio web: <a href="http://moisesluxuryremodeling.com">moisesluxuryremodeling.com</a></li>
            <li>Teléfonos: +813 720 9732 / +813 515 6403</li>
            <li>Ubicación: Tampa, Florida</li>
          </ul>
        </div>
        """
        ficha = parsear_sintesis_negocio(html=html, id_registro="img_2", fuente_imagen="tarjeta.png")
        self.assertEqual(ficha.propietario, "Auner Fuentes")
        self.assertEqual(ficha.negocio, "Remodeling")
        self.assertEqual(ficha.categoria, "remodelacion")
        self.assertEqual(ficha.telefono, "(813) 720-9732 / (813) 515-6403")
        self.assertEqual(ficha.ubicacion, "Tampa, Florida")
        self.assertEqual(ficha.sitio_web, "moisesluxuryremodeling.com")
        self.assertIn("moisesluxuryremodeling.com", ficha.enlaces[0])

    def test_parsear_ficha_google_lens_star_roofing(self) -> None:
        html = """<div class="mZJni Dn7Fzd" data-container-id="main-col" jsname="KFl8ub">
          <div class="n6owBd awi2gc"><span>La imagen muestra una tarjeta de presentación o anuncio de la empresa de techado </span><strong class="rQesXe MPyX">Star 2024 Roofing</strong>.</div>
          <div class="ZLzG0d" role="heading">Información de contacto y detalles en la imagen</div>
          <ul class="XSq4R"><li class="Z1qcYe"><span><strong>Nombre de la empresa:</strong> Star 2024 Roofing</span></li>
          <li class="Z1qcYe"><span><strong>Número de licencia:</strong> <code>#1145136</code></span></li>
          <li class="Z1qcYe"><span><strong>Ejecutivo de ventas:</strong> Ulises</span></li>
          <li class="Z1qcYe"><span><strong>Teléfono:</strong> (949) 279-2125</span></li>
          <li class="Z1qcYe"><span><strong>Correo electrónico:</strong> Ulisesym45@gmail.com</span></li>
          <li class="Z1qcYe"><span><strong>Servicios:</strong> Presupuestos gratis</span></li></ul>
        </div>"""
        ficha = parsear_sintesis_negocio(html=html, id_registro="star_1", fuente_imagen="star.jpg")
        self.assertEqual(ficha.negocio, "Star 2024 Roofing")
        self.assertEqual(ficha.propietario, "Ulises")
        self.assertEqual(ficha.licencia, "#1145136")
        self.assertEqual(ficha.telefono, "(949) 279-2125")
        self.assertEqual(ficha.correo_electronico, "Ulisesym45@gmail.com")
        self.assertEqual(ficha.categoria, "techado")

    def test_parsear_ficha_google_lens_moises_luxury(self) -> None:
        html = """<div class="mZJni Dn7Fzd" data-container-id="main-col" jsname="KFl8ub">
          <div class="n6owBd awi2gc"><span>La tarjeta de presentación muestra la información de contacto de </span><strong class="rQesXe MPyX">Moises Luxury Remodeling</strong>, un negocio de remodelación en Tampa, Florida.</div>
          <ul class="XSq4R"><li class="Z1qcYe"><span><strong>Propietario:</strong> Auner Fuentes</span></li>
          <li class="Z1qcYe"><span><strong>Sitio web:</strong> <a class="H23r4e" target="_blank" href="https://moisesluxuryremodeling.com/en/home/">moisesluxuryremodeling.com</a></span></li>
          <li class="Z1qcYe"><span><strong>Teléfonos:</strong> +1 (813) 720-9732 y +1 (813) 515-6403</span></li>
          <li class="Z1qcYe"><span><strong>Ubicación:</strong> Tampa, FL</span></li></ul>
        </div>"""
        ficha = parsear_sintesis_negocio(html=html, id_registro="moises_1", fuente_imagen="moises.jpg")
        self.assertEqual(ficha.negocio, "Moises Luxury Remodeling")
        self.assertEqual(ficha.propietario, "Auner Fuentes")
        self.assertIn("moisesluxuryremodeling.com", ficha.sitio_web)
        self.assertIn("(813) 720-9732", ficha.telefono)
        self.assertIn("(813) 515-6403", ficha.telefono)
        self.assertEqual(ficha.ubicacion, "Tampa, FL")
        self.assertEqual(ficha.categoria, "remodelacion")

    def test_parsear_tarjeta_g_construction_propietarios_multiples(self) -> None:
        texto = (
            "Información de la empresa y contacto en la tarjeta:\n\n"
            "• Negocio: G Construction LLC / Garcia's custom iron doors\n"
            "• Propietarios: Jose Garcia / Jr. Garcia (Owner)\n"
            "• Especialidad: Contratista general (cocinas, baños, duchas, techos, pintura, molduras, puertas, ventanas, aire acondicionado, terrazas, patios y pisos)\n"
            "• Dirección: 7715 North Freeway, Houston, TX 77037\n"
            "• Teléfonos: 832-274-9087 / 832-874-3676\n"
            "• Correo electrónico: jose@gconstructionhouston.com / www.gconstructionllctx.com"
        )
        ficha = parsear_sintesis_negocio(texto=texto, id_registro="g_const_1", fuente_imagen="g_const.jpg")
        self.assertEqual(ficha.negocio, "G Construction LLC / Garcia's custom iron doors")
        self.assertEqual(ficha.propietario, "Jose Garcia / Jr. Garcia (Owner)")
        self.assertIn("Contratista general", ficha.categoria)
        self.assertEqual(ficha.ubicacion, "7715 North Freeway, Houston, TX 77037")
        self.assertIn("(832) 274-9087", ficha.telefono)
        self.assertIn("(832) 874-3676", ficha.telefono)
        self.assertEqual(ficha.correo_electronico, "jose@gconstructionhouston.com")
        self.assertEqual(ficha.sitio_web, "www.gconstructionllctx.com")

    def test_parsear_servicios_ofrecidos_y_citas_garcia_construction(self) -> None:
        texto = (
            "Información de contacto y servicios\n"
            "Propietario: Tomás García\n"
            "Teléfono: (919) 747-1050\n"
            "Correo electrónico: tomastgarcia19@gmail.com / owner@garcia-construction.com\n"
            "Sitio web: [garcia-construction.com](https://garcia-construction.com/)\n"
            "Área principal: Raleigh, Chapel Hill y zonas cercanas en Carolina del Norte, EE. UU. [[1](https://nextdoor.com/pages/garcia-construction-general-contractor-raleigh-nc/), [2](https://www.facebook.com/garciaconstruction.co/)]\n"
            "Servicios ofrecidos\n"
            "Decks (Terrazas)\n"
            "Painting (Pintura interior y exterior)\n"
            "Additions (Ampliaciones)\n"
            "Drywalling (Tablaroca / Panel de yeso)\n"
            "Concrete (Concreto)\n"
            "Sun Rooms (Salas de sol / Solariums)\n"
            "Screen Porches (Porches con mosquitero)\n"
            "Roofing (Techados)\n"
            "Interior & Exterior Renovations (Renovaciones interiores y exteriores) [[1](https://www.facebook.com/garciaconstruction.co/)]"
        )
        ficha = parsear_sintesis_negocio(texto=texto, id_registro="garcia_1", fuente_imagen="garcia.jpg")
        self.assertEqual(ficha.propietario, "Tomas Garcia")
        self.assertEqual(ficha.telefono, "(919) 747-1050")
        self.assertIn("tomastgarcia19@gmail.com", ficha.correo_electronico)
        self.assertIn("owner@garcia-construction.com", ficha.correo_electronico)
        self.assertEqual(ficha.sitio_web, "garcia-construction.com")
        self.assertEqual(ficha.negocio, "Garcia Construction")
        self.assertEqual(ficha.ubicacion, "Raleigh, Chapel Hill y zonas cercanas en Carolina del Norte, EE. UU.")
        self.assertIn("Decks (Terrazas)", ficha.categoria)
        self.assertIn("Roofing (Techados)", ficha.categoria)
        self.assertTrue(any("nextdoor.com" in e for e in ficha.enlaces))
        self.assertTrue(any("facebook.com" in e for e in ficha.enlaces))

    def test_clasificacion_etiquetas_variantes_ingles_y_calificadores(self) -> None:
        texto = (
            "Company name: Apex Solutions\n"
            "Personal email: dev@apex.com\n"
            "Work phone: 555-123-4567\n"
            "Office address: 123 Tech Way, Austin, TX"
        )
        ficha = parsear_sintesis_negocio(texto=texto)
        self.assertEqual(ficha.negocio, "Apex Solutions")
        self.assertEqual(ficha.correo_electronico, "dev@apex.com")
        self.assertEqual(ficha.telefono, "(555) 123-4567")
        self.assertEqual(ficha.ubicacion, "123 Tech Way, Austin, TX")


