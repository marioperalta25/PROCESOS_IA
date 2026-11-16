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
