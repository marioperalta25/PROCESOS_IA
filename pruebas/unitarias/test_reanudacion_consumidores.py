"""Cancelar y continuar desde el original usando los procesadores reales y motores simulados."""

from contextlib import ExitStack
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.comun.gestor_reanudacion_tabular import GestorReanudacionTabular
from procesos_ia.aplicacion.ia_web.conversacional.procesador_modo_ia import ProcesadorModoIA
from procesos_ia.aplicacion.ia_web.motores.servicio_procesamiento_web import ServicioProcesamientoWeb
from procesos_ia.aplicacion.ia_web.visual_1a1.procesador_archivo_urls import ProcesadorArchivoUrls
from procesos_ia.dominio.ia_web.ficha_negocio import FichaNegocioLens
from procesos_ia.dominio.excepciones import ErrorPersistenciaTabular
from procesos_ia.dominio.reanudacion import AccionReanudacion
from procesos_ia.infraestructura.archivos.escritor_csv import guardar_filas_csv
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb


class PruebaReanudacionConsumidores(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)
        self.enrutador = EnrutadorSalidas(self.raiz / "salidas")
        self.origen = self.raiz / "entrada.csv"
        self.filas = [{"nombre": n, "url": f"https://ejemplo.test/{n}.png"} for n in ("Ana", "Beto", "Carla")]
        guardar_filas_csv(self.filas, self.origen)
        self.configuracion = ConfiguracionWeb()
        self.gestor = MagicMock()
        self.gestor.abrir_nueva_pestana = AsyncMock()
        self.gestor.navegar_o_reutilizar = AsyncMock()
        self.gestor.cerrar_navegador = AsyncMock()

    def preparar(self, modulo="modo_ia", instrucciones="Evaluar", columnas=None, opciones=None):
        return GestorReanudacionTabular(self.enrutador).preparar_trabajo(
            self.origen, modulo, instrucciones, columnas or ["nombre"], self.filas,
            opciones if opciones is not None else {"hoja": None},
        )

    def leer_exportacion(self, ruta):
        with ruta.open(encoding="utf-8-sig", newline="") as archivo:
            return list(csv.DictReader(archivo))

    def parches_google(self, respuestas):
        parches = ExitStack()
        modulo = "procesos_ia.aplicacion.ia_web.conversacional.procesador_modo_ia."
        for nombre, valor in (("activar_modo_ia", True), ("enviar_prompt_modo_ia", True),
                              ("marcar_turnos_previos_modo_ia", 0)):
            parches.enter_context(patch(modulo + nombre, new=AsyncMock(return_value=valor)))
        parches.enter_context(patch(modulo + "esperar_respuesta_modo_ia", new=AsyncMock(side_effect=respuestas)))
        parches.enter_context(patch(modulo + "verificar_conexion_internet", return_value=True))
        parches.enter_context(patch(modulo + "asyncio.sleep", new=AsyncMock()))
        return parches

    async def test_google_continua_la_misma_copia_sin_repetir_exitosos(self):
        original = self.origen.read_bytes()
        trabajo = self.preparar()
        procesador = ProcesadorModoIA(self.gestor, self.enrutador, self.configuracion)
        cancelado = False

        def cancelar(actual, total, detalle):
            nonlocal cancelado
            cancelado = actual == 2

        with self.parches_google(["Listo", "[FILA 1]: Primero\n[FILA 2]: Segundo"]):
            resultados, primera = await procesador.ejecutar(
                trabajo.filas_pendientes, "Evaluar", ["nombre"], tamano_lote=2,
                callback_progreso=cancelar, verificador_cancelacion=lambda: cancelado,
                generar_auditoria_md=False, trabajo_tabular=trabajo,
            )
        self.assertEqual(len(resultados), 2)
        self.assertIn("cancelados", primera.parts)
        self.enrutador = EnrutadorSalidas(self.enrutador.raiz)
        recuperado = self.preparar()
        self.assertEqual([f["_id_registro"] for f in recuperado.filas_pendientes], ["fila_3"])
        avances = []
        with self.parches_google(["Listo", "[FILA 1]: Tercero"]):
            nuevos, final = await procesador.ejecutar(
                recuperado.filas_pendientes, "Evaluar", ["nombre"], trabajo_tabular=recuperado,
                callback_progreso=lambda a, t, d: avances.append((a, t)), generar_auditoria_md=False,
            )
        self.assertEqual(len(nuevos), 1)
        self.assertEqual(primera.name, final.name)
        self.assertEqual([f["evaluacion_ia"] for f in self.leer_exportacion(final)], ["Primero", "Segundo", "Tercero"])
        self.assertEqual(avances, [(2, 3), (3, 3)])
        self.assertEqual(self.origen.read_bytes(), original)

    async def test_gemini_y_deepseek_correlacionan_ids_y_recuperan_solo_pendientes(self):
        modulo = "procesos_ia.aplicacion.ia_web.motores.servicio_procesamiento_web."
        for motor in ("gemini", "deepseek"):
            with self.subTest(motor=motor):
                servicio = ServicioProcesamientoWeb(self.gestor, self.configuracion, self.enrutador)
                trabajo = self.preparar(motor)
                with patch(modulo + "asyncio.sleep", new=AsyncMock()), \
                     patch(modulo + "enviar_prompt_" + motor, new=AsyncMock(return_value=True)), \
                     patch(modulo + "esperar_respuesta_" + motor, new=AsyncMock(return_value='[{"id":2,"calificacion":"B"},{"id":1,"calificacion":"A"}]')):
                    await servicio.procesar_csv(
                        motor, self.origen, ["nombre"], "Evaluar", tamano_lote=2,
                        callback_progreso=lambda a, t, d: servicio.cancelar() if a == 2 else None,
                        trabajo_tabular=trabajo, generar_auditoria_md=False,
                    )
                recuperado = self.preparar(motor)
                self.assertEqual(recuperado.resumen.exitosos, 2)
                with patch(modulo + "asyncio.sleep", new=AsyncMock()), \
                     patch(modulo + "enviar_prompt_" + motor, new=AsyncMock(return_value=True)) as enviar, \
                     patch(modulo + "esperar_respuesta_" + motor, new=AsyncMock(return_value='[{"id":1,"calificacion":"C"}]')):
                    nuevos, salida = await servicio.procesar_csv(
                        motor, self.origen, ["nombre"], "Evaluar", trabajo_tabular=recuperado,
                        generar_auditoria_md=False,
                    )
                self.assertEqual(len(nuevos), 1)
                self.assertEqual(enviar.await_count, 1)
                self.assertEqual([f["calificacion"] for f in self.leer_exportacion(salida)], ["A", "B", "C"])

    async def test_lens_cuenta_filas_originales_antes_de_desglosar_telefonos(self):
        opciones = {"hoja": None, "columna_imagen": "url"}
        trabajo = self.preparar("imagenes", "", ["url"], opciones)
        ejecutor = AsyncMock(return_value=FichaNegocioLens(estado_ia="EXITOSO", telefono="8322749087 / 8328743676"))
        procesador = ProcesadorArchivoUrls(self.gestor, self.enrutador, self.configuracion, ejecutor)
        cancelado = False

        def cancelar(actual, total, detalle):
            nonlocal cancelado
            cancelado = actual == 1

        with patch("asyncio.sleep", new=AsyncMock()):
            await procesador.ejecutar(
                self.origen, "url", trabajo_tabular=trabajo, callback_progreso=cancelar,
                verificador_cancelacion=lambda: cancelado, generar_auditoria_md=False,
            )
        recuperado = self.preparar("imagenes", "", ["url"], opciones)
        self.assertEqual((recuperado.resumen.exitosos, recuperado.resumen.pendientes), (1, 2))
        ejecutor.reset_mock()
        ejecutor.return_value = FichaNegocioLens(estado_ia="EXITOSO", telefono="8322749087")
        with patch("asyncio.sleep", new=AsyncMock()):
            _, salida = await procesador.ejecutar(self.origen, "url", trabajo_tabular=recuperado, generar_auditoria_md=False)
        self.assertEqual(ejecutor.call_args_list[0].kwargs["id_registro"], "fila_2")
        self.assertEqual(ejecutor.await_count, 2)
        self.assertEqual(len(self.leer_exportacion(salida)), 4)
        self.assertEqual(self.preparar("imagenes", "", ["url"], opciones).resumen.exitosos, 3)

    async def test_fallo_de_disco_durante_cancelacion_no_anuncia_avance(self):
        trabajo = self.preparar()
        procesador = ProcesadorModoIA(self.gestor, self.enrutador, self.configuracion)
        avance = MagicMock()
        cancelado = False

        def fallar(cambios):
            nonlocal cancelado
            cancelado = True
            raise ErrorPersistenciaTabular("Disco lleno")

        with self.parches_google(["Listo", "[FILA 1]: Primero"]), \
             patch.object(trabajo, "confirmar", side_effect=fallar):
            with self.assertRaises(ErrorPersistenciaTabular):
                await procesador.ejecutar(
                    trabajo.filas_pendientes, "Evaluar", tamano_lote=1, trabajo_tabular=trabajo,
                    callback_progreso=avance, verificador_cancelacion=lambda: cancelado,
                    generar_auditoria_md=False,
                )
        avance.assert_not_called()
        self.assertEqual(self.preparar().resumen.exitosos, 0)

    async def test_recuperar_exportacion_no_abre_navegador_ni_reenvia(self):
        trabajo = self.preparar()
        with self.assertRaises(ErrorPersistenciaTabular):
            with trabajo.abrir(self.enrutador, "resultado.csv"):
                trabajo.confirmar([{**f, "_estado_ia": "EXITOSO", "evaluacion_ia": "Guardado"} for f in trabajo.filas])
                trabajo.finalizar("completados", exportador=MagicMock(side_effect=OSError("Archivo ocupado")))
        recuperado = self.preparar()
        recuperado.seleccionar(AccionReanudacion.RECUPERAR_RESULTADOS)
        procesador = ProcesadorModoIA(self.gestor, self.enrutador, self.configuracion)
        resultados, ruta = await procesador.ejecutar([], "Evaluar", trabajo_tabular=recuperado)
        self.assertEqual(resultados, [])
        self.assertEqual(len(self.leer_exportacion(ruta)), 3)
        self.gestor.abrir_nueva_pestana.assert_not_awaited()
        self.gestor.cerrar_navegador.assert_not_awaited()

    async def test_reintento_google_completado_no_se_clasifica_por_el_error_transitorio(self):
        trabajo = self.preparar()
        procesador = ProcesadorModoIA(self.gestor, self.enrutador, self.configuracion)
        modulo = "procesos_ia.aplicacion.ia_web.conversacional.procesador_modo_ia."
        with self.parches_google(["Listo", "[FILA 1]: A\n[FILA 2]: B\n[FILA 3]: C"]), \
             patch(modulo + "enviar_prompt_modo_ia", new=AsyncMock(side_effect=[False, True, True])):
            _, salida = await procesador.ejecutar(
                trabajo.filas_pendientes, "Evaluar", trabajo_tabular=trabajo, generar_auditoria_md=False,
            )
        self.assertIn("completados", salida.parts)

    async def test_recuperar_fallo_de_envio_elimina_el_error_anterior(self):
        servicio = ServicioProcesamientoWeb(self.gestor, self.configuracion, self.enrutador)
        modulo = "procesos_ia.aplicacion.ia_web.motores.servicio_procesamiento_web."
        with patch(modulo + "enviar_prompt_gemini", new=AsyncMock(return_value=False)):
            await servicio.procesar_csv(
                "gemini", self.origen, ["nombre"], "Evaluar", trabajo_tabular=self.preparar("gemini"),
                generar_auditoria_md=False,
            )
        trabajo = self.preparar("gemini")
        self.assertEqual(trabajo.resumen.fallidos, 3)
        with patch(modulo + "asyncio.sleep", new=AsyncMock()), \
             patch(modulo + "enviar_prompt_gemini", new=AsyncMock(return_value=True)), \
             patch(modulo + "esperar_respuesta_gemini", new=AsyncMock(return_value='[{"valor":"A"},{"valor":"B"},{"valor":"C"}]')):
            _, salida = await servicio.procesar_csv(
                "gemini", self.origen, ["nombre"], "Evaluar", trabajo_tabular=trabajo,
                generar_auditoria_md=False,
            )
        self.assertIn("completados", salida.parts)
        filas = self.leer_exportacion(salida)
        self.assertTrue(all(not f.get("error_inferencia") for f in filas))
