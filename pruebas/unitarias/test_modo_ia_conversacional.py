"""Pruebas unitarias para el procesamiento conversacional y formateo de lotes en Modo IA."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.conversacional.formateador_lotes_chat import (
    compactar_instrucciones_prompt,
    construir_mensaje_lote_datos,
    construir_prompt_inicial_conversacion,
    construir_prompt_lote_chat,
)
from procesos_ia.aplicacion.ia_web.conversacional.procesador_modo_ia import (
    ProcesadorModoIA,
    mapear_respuestas_lote,
)
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb


class PruebaModoIAConversacional(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.enrutador = EnrutadorSalidas(self.raiz)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_compactar_instrucciones_prompt(self) -> None:
        crudo = (
            "INSTRUCCIONES   GENERALES\n\n\n\n"
            "--------------------------------------------------------------------------------\n"
            "Regla 1:   evaluar   apellidos.\n\n\n"
            "================================================================================\n"
            "Regla 2: machear."
        )
        compacto = compactar_instrucciones_prompt(crudo)
        self.assertNotIn("--------------------------------------------------------------------------------", compacto)
        self.assertIn("---", compacto)
        self.assertNotIn("\n\n\n", compacto)
        self.assertNotIn("   ", compacto)
        self.assertIn("INSTRUCCIONES GENERALES", compacto)
        self.assertIn("Regla 1: evaluar apellidos.", compacto)

    def test_construir_mensaje_lote_datos(self) -> None:
        filas = [
            {"empresa": "ABC Plumbing", "dueno": "Juan Perez"},
            {"empresa": "XYZ Cleaners", "dueno": "Maria Lopez"},
        ]
        msg = construir_mensaje_lote_datos(filas, columnas_seleccionadas=["empresa", "dueno"], indice_inicio=10)
        lineas = msg.splitlines()
        self.assertEqual(len(lineas), 2)
        self.assertTrue(lineas[0].startswith("[FILA 10]:"))
        self.assertIn("ABC Plumbing", lineas[0])
        self.assertIn("Juan Perez", lineas[0])
        self.assertTrue(lineas[1].startswith("[FILA 11]:"))
        self.assertIn("XYZ Cleaners", lineas[1])
        self.assertIn("Maria Lopez", lineas[1])

    def test_mapear_respuestas_lote_etiquetas_secuenciales(self) -> None:
        texto_google = (
            "LATINO CONFIRMADO - MACHEA\n"
            "LATINO CONFIRMADO - NO MACHEA\n"
            "NO LATINO - MACHEA\n"
        )
        lote = [
            {"empresa": "E1", "dueno": "D1"},
            {"empresa": "E2", "dueno": "D2"},
            {"empresa": "E3", "dueno": "D3"},
        ]
        res = mapear_respuestas_lote(
            texto_resp=texto_google, datos={}, lote_actual=lote, indice_base=1,
        )
        self.assertEqual(len(res), 3)
        self.assertEqual(res[0]["evaluacion_ia"], "LATINO CONFIRMADO - MACHEA")
        self.assertEqual(res[1]["evaluacion_ia"], "LATINO CONFIRMADO - NO MACHEA")
        self.assertEqual(res[2]["evaluacion_ia"], "NO LATINO - MACHEA")

    def test_mapear_respuestas_lote_con_filas_explicitadas(self) -> None:
        texto = "[FILA 5]: LATINO CONFIRMADO - MACHEA\n[FILA 6]: NO LATINO - NO MACHEA"
        lote = [{"e": "A"}, {"e": "B"}]
        res = mapear_respuestas_lote(texto, {}, lote, indice_base=5)
        self.assertEqual(res[0]["evaluacion_ia"], "LATINO CONFIRMADO - MACHEA")
        self.assertEqual(res[1]["evaluacion_ia"], "NO LATINO - NO MACHEA")

    def test_mapear_respuestas_lote_con_frases_de_cortesia(self) -> None:
        texto = (
            "LATINO CONFIRMADO - MACHEA\n"
            "LATINO CONFIRMADO - NO MACHEA\n"
            "Envía el siguiente lote de registros cuando estés listo para continuar con el procesamiento.\n"
        )
        lote = [{"e": "A"}, {"e": "B"}]
        res = mapear_respuestas_lote(texto, {}, lote, indice_base=1)
        self.assertEqual(res[0]["evaluacion_ia"], "LATINO CONFIRMADO - MACHEA")
        self.assertEqual(res[1]["evaluacion_ia"], "LATINO CONFIRMADO - NO MACHEA")

    async def test_ciclo_conversacional_lotes_por_conversacion(self) -> None:
        gestor = MagicMock()
        pestana_mock = MagicMock()
        pestana_mock.get = AsyncMock()
        pestana_mock.evaluate = AsyncMock(return_value=0)
        gestor.abrir_nueva_pestana = AsyncMock(return_value=pestana_mock)
        gestor.cerrar_navegador = AsyncMock()

        config = ConfiguracionWeb()
        procesador = ProcesadorModoIA(gestor, self.enrutador, config)

        filas = [{"col": f"val_{i}"} for i in range(6)]
        modulo = "procesos_ia.aplicacion.ia_web.conversacional.procesador_modo_ia."

        prompts_enviados = []

        async def mock_enviar(pestana, prompt):
            prompts_enviados.append(prompt)
            return True

        with patch(modulo + "verificar_conexion_internet", return_value=True), \
             patch(modulo + "activar_modo_ia", new=AsyncMock(return_value=True)), \
             patch(modulo + "enviar_prompt_modo_ia", side_effect=mock_enviar), \
             patch(modulo + "esperar_respuesta_modo_ia", new=AsyncMock(return_value="LATINO CONFIRMADO - MACHEA\nLATINO CONFIRMADO - MACHEA")):

            resultados, salida = await procesador.ejecutar(
                filas=filas,
                instrucciones="Clasifica empresas.",
                tamano_lote=2,
                lotes_por_conversacion=2,
            )

            self.assertEqual(len(resultados), 6)
            self.assertIsNotNone(salida)
            self.assertEqual(len(prompts_enviados), 5)
            self.assertIn("Clasifica empresas.", prompts_enviados[0])
            self.assertIn("[FILA 1]:", prompts_enviados[1])
            self.assertIn("[FILA 1]:", prompts_enviados[2])
            self.assertIn("Clasifica empresas.", prompts_enviados[3])
            self.assertIn("[FILA 1]:", prompts_enviados[4])

    def test_mapear_respuestas_lote_separa_columnas_pipe_y_filtra_encabezados(self) -> None:
        texto = "Claro\nResultados:\n[FILA 1]: Sí | Techos y cubiertas\n[FILA 2]: No | Plomería"
        lote = [{"desc": "A"}, {"desc": "B"}]
        res = mapear_respuestas_lote(texto, None, lote, indice_base=1)
        self.assertEqual(res[0]["evaluacion_col_1"], "Sí")
        self.assertEqual(res[0]["evaluacion_col_2"], "Techos y cubiertas")
        self.assertEqual(res[1]["evaluacion_col_1"], "No")
        self.assertEqual(res[1]["evaluacion_col_2"], "Plomería")

        texto_sin_etiquetas = "Resultados:\nSí | Techos\nNo | Plomería"
        res2 = mapear_respuestas_lote(texto_sin_etiquetas, None, lote, indice_base=1)
        self.assertEqual(res2[0]["evaluacion_col_1"], "Sí")
        self.assertEqual(res2[1]["evaluacion_col_2"], "Plomería")

    def test_mapear_respuestas_lote_no_sobrescribe_columnas_originales_y_agrega_ia(self) -> None:
        lote = [
            {"negocio": "JMP", "categoria": "Contratista", "_id_registro": "fila_1", "_estado_ia": "PENDIENTE"},
            {"negocio": "Lilian", "categoria": "", "_id_registro": "fila_2", "_estado_ia": "PENDIENTE"},
        ]
        datos = {"resultados": [
            {"id": 1, "categoria": "Construction Company", "habla_espanol": "Sí"},
            {"id": 2, "categoria": "House Cleaning", "habla_espanol": "No"},
        ]}
        res = mapear_respuestas_lote("", datos, lote, indice_base=1)
        self.assertEqual(res[0]["categoria"], "Contratista")
        self.assertEqual(res[0]["categoria_ia"], "Construction Company")
        self.assertEqual(res[0]["habla_espanol"], "Sí")
        self.assertEqual(res[1]["categoria"], "")
        self.assertEqual(res[1]["categoria_ia"], "House Cleaning")

    def test_guardar_enriquecido_preserva_telefono_original_y_fecha_xlsx(self) -> None:
        import csv, tempfile
        from datetime import datetime
        from procesos_ia.aplicacion.ia_web.comun.guardador_extracciones import guardar_filas_enriquecidas_csv
        from procesos_ia.infraestructura.archivos.lector_xlsx import _celda_a_texto

        self.assertEqual(_celda_a_texto(datetime(2026, 11, 16, 0, 0, 0)), "2026-11-16")
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "salida.csv"
            filas = [{"telefono": "4013008353", "_id_registro": "fila_1", "_estado_ia": "EXITOSO", "categoria_ia": "Cleaning"}]
            guardar_filas_enriquecidas_csv(filas, ruta)
            leido = list(csv.DictReader(ruta.open(encoding="utf-8-sig")))
            self.assertEqual(leido[0]["telefono"], "4013008353")

            ruta2 = Path(tmp) / "salida_ia_tel.csv"
            filas2 = [{"url": "https://x.test", "_id_registro": "fila_1", "_estado_ia": "EXITOSO", "telefonos": "4013008353 / 8574525571"}]
            guardar_filas_enriquecidas_csv(filas2, ruta2)
            leido2 = list(csv.DictReader(ruta2.open(encoding="utf-8-sig")))
            self.assertEqual(len(leido2), 2)
            self.assertEqual(leido2[0]["telefonos"], "(401) 300-8353")

    async def test_servicio_web_usa_respaldo_texto_y_reintenta_lote_incompleto(self) -> None:
        from procesos_ia.aplicacion.ia_web.motores.servicio_procesamiento_web import ServicioProcesamientoWeb

        gestor = MagicMock()
        gestor.abrir_nueva_pestana = AsyncMock(return_value=MagicMock())
        gestor.cerrar_navegador = AsyncMock()
        servicio = ServicioProcesamientoWeb(gestor, ConfiguracionWeb(), self.enrutador)
        filas = [{"negocio": "A"}, {"negocio": "B"}]
        respuestas = iter(["[FILA 1]: Solo uno", "[FILA 1]: Sí | Techos\n[FILA 2]: No | Pintura"])
        mod = "procesos_ia.aplicacion.ia_web.motores.servicio_procesamiento_web."
        with patch(mod + "enviar_prompt_gemini", new=AsyncMock(return_value=True)), \
             patch(mod + "esperar_respuesta_gemini", side_effect=lambda *a, **kw: next(respuestas)), \
             patch(mod + "iniciar_nuevo_chat_gemini", new=AsyncMock(return_value=True)) as chat_mock:
            res, _ = await servicio._procesar_flujo_texto_lotes(
                motor="gemini", pestana=MagicMock(), filas=filas, columnas=["negocio"],
                instrucciones="Evalúa", tamano_lote=2, rotacion=5, stem="test_fallback",
                cb_prog=None, cb_log=None, generar_auditoria_md=False,
            )
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["evaluacion_col_1"], "Sí")
        self.assertEqual(res[1]["evaluacion_col_2"], "Pintura")
        chat_mock.assert_awaited_once()
