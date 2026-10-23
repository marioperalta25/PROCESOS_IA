"""Continuidad reciente, memoria manual y medidas sin inferencias adicionales."""

from pathlib import Path
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from procesos_ia.aplicacion.conversacion import ServicioConversacion
from procesos_ia.dominio.excepciones import ErrorProcesamiento, OperacionCancelada
from procesos_ia.infraestructura.ollama.parametros_chat import cargar_parametros_chat
from procesos_ia.infraestructura.persistencia.repositorio_chat import RepositorioChat


class PruebaContextoRapido(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.p = cargar_parametros_chat()
        self.repo = RepositorioChat(Path(temporal.name), self.p)
        self.generar = MagicMock(return_value="Respuesta")
        self.s = ServicioConversacion(self.repo, self.generar, self.p)

    def turno(self, datos, usuario, respuesta):
        for rol, texto in [("user", usuario), ("assistant", respuesta)]:
            datos["mensajes"].append({"id": str(len(datos["mensajes"])), "rol": rol,
                                       "texto": texto, "estado": "completo"})
        datos["modelo"] = "simulado"

    def test_varios_turnos_breves_caben_en_2048_sin_borrar_historial(self):
        datos = self.repo.nuevo()
        for i in range(6):
            self.turno(datos, f"Pregunta {i}: " + "a" * 40, f"Respuesta {i}: " + "b" * 80)
        contexto, reducido = self.s.preparar_contexto(datos, "Continúa", 2048)
        self.assertFalse(reducido)
        self.assertEqual(len(contexto), 14)
        self.assertEqual(contexto[-3]["content"], datos["mensajes"][-2]["texto"])
        self.assertEqual(len(datos["mensajes"]), 12)

    def test_ventana_es_un_sufijo_sin_turnos_partidos_ni_estados_pendientes(self):
        datos = self.repo.nuevo()
        for i in range(10):
            self.turno(datos, f"Pregunta {i}" * 20, f"Respuesta {i}" * 20)
        datos["mensajes"].append({"id": "pendiente", "rol": "user", "texto": "No confirmado",
                                   "estado": "cancelado"})
        contexto, reducido = self.s.preparar_contexto(datos, "Actual", 2048)
        self.assertTrue(reducido)
        historial = contexto[1:-1]
        self.assertEqual([m["role"] for m in historial], ["user", "assistant"] * (len(historial) // 2))
        esperado = datos["mensajes"][:-1][-len(historial):]
        self.assertEqual([m["content"] for m in historial], [m["texto"] for m in esperado])

    def test_memoria_antigua_extensa_no_bloquea_ni_se_sobrescribe(self):
        datos = self.repo.nuevo()
        datos["resumen"] = "Memoria anterior " * 200
        self.turno(datos, "Pregunta reciente", "Respuesta reciente")
        final, aviso = self.s.responder(datos, "Sigue", "simulado", 2048, 0.1, Event())
        self.assertEqual(final["resumen"], datos["resumen"])
        self.assertIn(self.p["textos"]["memoria_omitida"], aviso)
        self.assertFalse(final["ultima_inferencia"]["memoria_incluida"])
        self.assertIn("Respuesta reciente", str(self.generar.call_args.args[0]))
        self.generar.assert_called_once()

    def test_memoria_validada_cuenta_su_prefijo_y_se_reutiliza_al_reabrir(self):
        with self.assertRaises(ErrorProcesamiento):
            self.s.validar_memoria("a" * 380)
        datos = self.repo.nuevo()
        datos["resumen"] = "El usuario prefiere respuestas breves."
        self.s.validar_memoria(datos["resumen"])
        final, _ = self.s.responder(datos, "Hola", "simulado", 2048, 0.1, Event())
        self.generar.reset_mock()
        reabierto = self.repo.leer(final["id"])
        self.generar.assert_not_called()
        self.s.responder(reabierto, "Otra", "simulado", 2048, 0.1, Event())
        self.assertEqual(self.generar.call_args.args[0][1]["content"],
                         self.p["textos"]["prefijo_resumen"] + datos["resumen"])
        self.generar.assert_called_once()

    def test_metricas_no_contienen_texto_y_se_guardan_con_respuesta_confirmada(self):
        def generar(*args, **opciones):
            opciones["al_metricas"]({"prompt_eval_count": 100, "prompt_eval_duration": 5000})
            return "Texto privado simulado"
        self.generar.side_effect = generar
        final, _ = self.s.responder(self.repo.nuevo(), "Entrada privada", "simulado", 2048, 0.1, Event())
        metricas = self.repo.leer(final["id"])["ultima_inferencia"]
        self.assertEqual(metricas["prompt_eval_count"], 100)
        self.assertNotIn("privad", str(metricas))

    def test_cancelacion_del_transporte_no_confirma_fragmentos(self):
        def generar(*args, **opciones):
            opciones["al_fragmento"]("Parcial")
            raise OperacionCancelada()
        self.generar.side_effect = generar
        final, _ = self.s.responder(self.repo.nuevo(), "Hola", "simulado", 2048, 0.1, Event(),
                                     al_fragmento=MagicMock())
        self.assertEqual(len(final["mensajes"]), 1)
        self.assertEqual(final["mensajes"][0]["estado"], "cancelado")
        self.assertNotIn("ultima_inferencia", final)

    def test_calibra_con_respuestas_normales_sin_generaciones_adicionales(self):
        def generar(*args, **opciones):
            opciones["al_metricas"]({"prompt_eval_count": 400})
            return "Respuesta breve"
        self.generar.side_effect = generar
        datos = self.repo.nuevo()
        for _ in range(4):
            datos, _ = self.s.responder(datos, "a" * 800, "simulado", 2048, 0.1, Event())
        self.assertEqual(self.generar.call_count, 4)
        self.assertGreater(datos["ultima_inferencia"]["bytes_por_token_estimados"],
                           self.p["limites"]["bytes_por_token_estimados"])
        self.assertEqual(datos["ultima_inferencia"]["prompt_eval_count"], 400)

    def test_actualizar_catalogo_invalida_estimacion_sin_inferir(self):
        from procesos_ia.interfaz.navegacion import NavegacionVistas
        mensajes = [{"content": "a" * 1000}]
        for _ in range(3):
            self.s.estimador.registrar("simulado", 2048, mensajes, {"prompt_eval_count": 300}, 1280)
        self.assertGreater(self.s.estimador.factor("simulado", 2048), 2)
        navegacion = NavegacionVistas(SimpleNamespace(_cliente_ollama=MagicMock()))
        navegacion.chat = SimpleNamespace(servicio=self.s, _selector=MagicMock())
        navegacion.actualizar_catalogo()
        self.assertEqual(self.s.estimador.factor("simulado", 2048), 2)
        self.generar.assert_not_called()
