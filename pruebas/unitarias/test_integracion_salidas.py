"""Conexion de consumidores reales con la organizacion comun, sin servicios externos."""

from dataclasses import replace
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from PySide6.QtWidgets import QApplication

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.motores.servicio_procesamiento_web import ServicioProcesamientoWeb
from procesos_ia.aplicacion.ia_web.conversacional.procesador_modo_ia import ProcesadorModoIA
from procesos_ia.aplicacion.ia_web.visual_1a1.servicio_ia_general import ServicioIAGeneral
from procesos_ia.dominio.ia_web.ficha_negocio import FichaNegocioLens
from procesos_ia.dominio.modelos import ConfiguracionTrabajo
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.interfaz.hilos import HiloCoordinadorTrabajo
from procesos_ia.interfaz.ia_web.vistas.vista_motores import VistaConfiguracionMotores


class PruebaIntegracionSalidas(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)
        self.enrutador = EnrutadorSalidas(self.raiz)
        self.configuracion = ConfiguracionWeb()
        self.gestor = MagicMock()
        self.gestor.abrir_nueva_pestana = AsyncMock()
        self.gestor.navegar_o_reutilizar = AsyncMock()
        self.gestor.cerrar_navegador = AsyncMock()

    async def test_motores_guardan_copias_y_conservan_la_primera(self) -> None:
        servicio = ServicioProcesamientoWeb(self.gestor, self.configuracion, self.enrutador)
        entrada = self.raiz / "clientes.csv"
        modulo = "procesos_ia.aplicacion.ia_web.motores.servicio_procesamiento_web."
        with ExitStack() as parches:
            parches.enter_context(patch(modulo + "asyncio.sleep", new=AsyncMock()))
            for motor in ("gemini", "deepseek"):
                parches.enter_context(patch(modulo + "enviar_prompt_" + motor, new=AsyncMock(return_value=True)))
                parches.enter_context(patch(modulo + "esperar_respuesta_" + motor,
                                            new=AsyncMock(return_value='[{"id": 1, "calificacion": "A"}]')))
                entrada.write_text("nombre\nAna\n", encoding="utf-8")
                _, anterior = await servicio.procesar_csv(motor, entrada, ["nombre"], "Evaluar")
                contenido = anterior.read_bytes()
                entrada.write_text("nombre\nBeto\n", encoding="utf-8")
                _, nueva = await servicio.procesar_csv(motor, entrada, ["nombre"], "Evaluar")
                self.assertIn(motor, nueva.parts)
                self.assertIn("completados", nueva.parts)
                self.assertEqual(nueva.stem, anterior.stem + "_copia1")
                self.assertEqual(anterior.read_bytes(), contenido)

    async def test_modo_ia_utiliza_su_rama_y_destino_personalizado(self) -> None:
        procesador = ProcesadorModoIA(self.gestor, self.enrutador, self.configuracion)
        modulo = "procesos_ia.aplicacion.ia_web.conversacional.procesador_modo_ia."
        with ExitStack() as parches:
            parches.enter_context(patch(modulo + "activar_modo_ia", new=AsyncMock(return_value=True)))
            parches.enter_context(patch(modulo + "enviar_prompt_modo_ia", new=AsyncMock(return_value=True)))
            parches.enter_context(patch(modulo + "esperar_respuesta_modo_ia",
                                        new=AsyncMock(return_value='{"resultados": [{"evaluacion": "A"}]}')))
            parches.enter_context(patch(modulo + "asyncio.sleep", new=AsyncMock()))
            _, salida = await procesador.ejecutar(
                [{"nombre": "Ana"}], "Evaluar", carpeta_salida=self.raiz / "elegida",
            )
        self.assertTrue(salida.is_relative_to(self.raiz / "elegida" / "extracciones" / "ia_general" / "modo_ia"))
        self.assertIn("completados", salida.parts)
        self.assertTrue(salida.is_file())
        self.gestor.cerrar_navegador.assert_awaited_once()

    async def test_lens_url_archivo_y_carpeta_comparten_rama_imagenes(self) -> None:
        servicio = ServicioIAGeneral(self.gestor, self.configuracion, self.enrutador)
        ficha = FichaNegocioLens(negocio="Demo", estado_ia="EXITOSO")
        ejecutor = AsyncMock(return_value=ficha)
        for procesador in (servicio._procesador_url, servicio._procesador_archivo, servicio._procesador_carpeta):
            procesador._ejecutor_lens = ejecutor
        entrada = self.raiz / "urls.csv"
        entrada.write_text("url\nhttps://ejemplo.test/foto.png\n", encoding="utf-8")
        imagenes = self.raiz / "imagenes"
        imagenes.mkdir()
        (imagenes / "foto.png").write_bytes(b"imagen sintetica")
        with patch("asyncio.sleep", new=AsyncMock()):
            _, url = await servicio.procesar_url_individual("https://ejemplo.test/foto.png")
            _, archivo = await servicio.procesar_csv_con_lens(entrada, "url")
            _, carpeta = await servicio.procesar_carpeta_imagenes_lens(imagenes)
        rama = self.raiz / "extracciones" / "ia_general" / "imagenes"
        for salida in (url, archivo, carpeta):
            self.assertTrue(salida.is_relative_to(rama))
            self.assertIn("completados", salida.parts)
            self.assertTrue(salida.is_file())
        self.assertEqual(servicio.ultima_salida, carpeta)

    async def test_fallo_de_motor_clasifica_sin_borrar_otras_salidas(self) -> None:
        servicio = ServicioProcesamientoWeb(self.gestor, self.configuracion, self.enrutador)
        entrada = self.raiz / "clientes.csv"
        entrada.write_text("nombre\nAna\n", encoding="utf-8")
        modulo = "procesos_ia.aplicacion.ia_web.motores.servicio_procesamiento_web."
        with patch(modulo + "enviar_prompt_gemini", new=AsyncMock(side_effect=RuntimeError("Fallo simulado"))):
            with self.assertRaises(RuntimeError):
                await servicio.procesar_csv("gemini", entrada, ["nombre"], "Evaluar")
        fallidos = self.raiz / "extracciones" / "gemini" / "fallidos"
        self.assertEqual(len(list(fallidos.iterdir())), 1)


class PruebaSalidaLocalEInterfaz(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_salida_local_se_clasifica_despues_de_cerrar_el_escritor(self) -> None:
        with tempfile.TemporaryDirectory() as temporal:
            enrutador = EnrutadorSalidas(Path(temporal))
            salida = enrutador.reservar_salida("ia_local", "resultado_procesado.csv", "clientes")
            coordinador = MagicMock()
            coordinador.procesar_siguiente_lote.return_value = False
            coordinador.cerrar.side_effect = lambda: salida.ruta.write_text("dato\nconfirmado\n", encoding="utf-8")
            hilo = HiloCoordinadorTrabajo(MagicMock(), coordinador=coordinador, salida=salida)
            hilo.run()
            self.assertIn("completados", salida.ruta.parts)
            self.assertTrue(salida.ruta.is_file())
            coordinador.cerrar.assert_called_once()

    def test_vista_motores_envia_ruta_y_columna_del_panel(self) -> None:
        with tempfile.TemporaryDirectory() as temporal:
            enrutador = EnrutadorSalidas(Path(temporal))
            entrada = Path(temporal) / "clientes.csv"
            entrada.write_text("nombre\nAna\n", encoding="utf-8")
            vista = VistaConfiguracionMotores(enrutador=enrutador)
            vista.panel_archivo.cargar_archivo(entrada)
            vista.txt_instrucciones.setPlainText("Evaluar")
            modulo = "procesos_ia.interfaz.ia_web.vistas.vista_motores.HiloProcesamientoWeb"
            with patch(modulo) as constructor:
                vista._ejecutar_procesamiento_web()
                self.assertEqual(constructor.call_args.kwargs["ruta_csv"], entrada)
                self.assertIsNone(constructor.call_args.kwargs["columna_imagen"])
            vista.close()

    def test_persistencia_local_real_respeta_el_nombre_de_copia(self) -> None:
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            enrutador = EnrutadorSalidas(raiz)
            entrada = raiz / "clientes.csv"
            entrada.write_text("texto\nEjemplo\n", encoding="utf-8")
            configuracion = ConfiguracionTrabajo(
                entrada, raiz, "simulado", 1, 1000, 512, 0.0, 10.0,
                ("texto",), "Evaluar", "csv", ("calificacion",),
            )
            inferencia = MagicMock()
            inferencia.procesar_lote.side_effect = lambda lote, cfg: [
                {"identificador": fila.identificador, "calificacion": "A"} for fila in lote
            ]
            rutas = []
            for _ in range(2):
                salida = enrutador.reservar_salida("ia_local", "resultado_procesado.csv", entrada.stem)
                hilo = HiloCoordinadorTrabajo(
                    replace(configuracion, directorio_salida=salida.directorio),
                    servicio_inferencia=inferencia, salida=salida,
                )
                errores = []
                hilo.senial_error.connect(errores.append)
                hilo.run()
                self.assertEqual(errores, [])
                self.assertIn("completados", salida.ruta.parts)
                self.assertTrue(salida.ruta.is_file())
                self.assertTrue((salida.directorio / "progreso.checkpoint").exists())
                rutas.append(salida.ruta)
            self.assertEqual(rutas[1].name, "resultado_procesado_copia1.csv")
            self.assertTrue(rutas[0].exists())

    def test_composicion_local_transmite_reserva_y_destino(self) -> None:
        from procesos_ia.interfaz.composicion_trabajo import iniciar_trabajo_local
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            configuracion = ConfiguracionTrabajo(
                raiz / "clientes.csv", raiz, "simulado", 1, 1000, 512, 0.0, 10.0,
                ("texto",), "Evaluar", "csv", ("calificacion",),
            )
            ventana = MagicMock()
            ventana._enrutador = EnrutadorSalidas(raiz)
            ventana.panel_archivos.raiz_salidas = raiz
            with patch("procesos_ia.interfaz.composicion_trabajo.HiloCoordinadorTrabajo") as constructor:
                iniciar_trabajo_local(ventana, configuracion)
                argumentos = constructor.call_args.kwargs
                self.assertEqual(argumentos["configuracion"].directorio_salida, argumentos["salida"].directorio)
                self.assertIs(argumentos["parent"], ventana)
                constructor.return_value.start.assert_called_once()
