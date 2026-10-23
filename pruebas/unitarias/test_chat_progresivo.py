"""Transporte NDJSON acotado, exclusión y confirmación de respuestas completas."""

from io import BytesIO
import json
from threading import Event
import unittest
from unittest.mock import MagicMock, patch

from procesos_ia.dominio.excepciones import ErrorProcesamiento, OperacionCancelada
from procesos_ia.infraestructura.ollama.chat import solicitar_chat
from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.ollama.parametros_chat import cargar_parametros_chat


class PruebaChatProgresivo(unittest.TestCase):
    def setUp(self):
        self.p = cargar_parametros_chat()
        self.cliente = ClienteHttpOllama()

    def flujo(self, eventos):
        return BytesIO(b"\n".join(json.dumps(e, ensure_ascii=False).encode("utf-8") for e in eventos) + b"\n")

    def evento(self, texto="", final=False, **extras):
        return {"done": final, "message": {"role": "assistant", "content": texto}, **extras}

    def solicitar(self, al_fragmento, cancelacion=None, al_metricas=None):
        return solicitar_chat(self.cliente, [{"role": "user", "content": "Consulta sintética"}],
                              "simulado", 2048, 0.1, self.p, al_fragmento=al_fragmento,
                              cancelacion=cancelacion, al_metricas=al_metricas)

    def test_fragmentos_llegan_antes_del_final_y_metricas_sin_texto(self):
        respuesta = self.flujo([self.evento("Español "), self.evento("ñ <b>literal</b>"),
                               self.evento(final=True, prompt_eval_count=25, eval_duration=100,
                                           prompt="No conservar", prompt_eval_cached_count=True)])
        trozos, metricas = [], {}
        def recibir(texto):
            self.assertLess(respuesta.tell(), len(respuesta.getvalue()))
            trozos.append(texto)
        with patch("urllib.request.urlopen", return_value=respuesta) as abrir:
            texto = self.solicitar(recibir, al_metricas=metricas.update)
        self.assertEqual(texto, "Español ñ <b>literal</b>")
        self.assertEqual(trozos, ["Español ", "ñ <b>literal</b>"])
        self.assertEqual(metricas, {"prompt_eval_count": 25, "eval_duration": 100})
        self.assertTrue(json.loads(abrir.call_args.args[0].data)["stream"])
        self.assertTrue(respuesta.closed)
        self.assertFalse(self.cliente._puerta_inferencia.locked())

    def test_corte_sin_final_y_eventos_invalidos_no_se_confirman_ni_reintentan(self):
        casos = [self.flujo([self.evento("Parcial")]), BytesIO(b"no es json\n"),
                 self.flujo([[]]), self.flujo([{"error": "Fallo simulado"}]),
                 self.flujo([self.evento(42, True)])]
        for respuesta in casos:
            with self.subTest(), patch("urllib.request.urlopen", return_value=respuesta) as abrir:
                with self.assertRaises(ErrorProcesamiento):
                    self.solicitar(MagicMock())
                abrir.assert_called_once()
                self.assertTrue(respuesta.closed)
                self.assertFalse(self.cliente._puerta_inferencia.locked())

    def test_limites_de_texto_linea_y_total_son_independientes(self):
        for clave, maximo, respuesta in [
            ("respuesta_bytes", 5, self.flujo([self.evento("abc"), self.evento("def", True)])),
            ("http_linea_bytes", 5, self.flujo([self.evento("Hola", True)])),
            ("http_bytes", 5, self.flujo([self.evento("Hola", True)])),
        ]:
            with self.subTest(clave=clave), patch("urllib.request.urlopen", return_value=respuesta):
                anterior = self.p["limites"][clave]
                self.p["limites"][clave] = maximo
                with self.assertRaises(ErrorProcesamiento):
                    self.solicitar(MagicMock())
                self.p["limites"][clave] = anterior
                self.assertTrue(respuesta.closed)

    def test_cancelacion_cierra_respuesta_y_libera_puerta(self):
        cancelar = Event()
        respuesta = self.flujo([self.evento("Parcial"), self.evento("No leer", True)])
        with patch("urllib.request.urlopen", return_value=respuesta) as abrir:
            with self.assertRaises(OperacionCancelada):
                self.solicitar(lambda texto: cancelar.set(), cancelar)
            abrir.assert_called_once()
        self.assertTrue(respuesta.closed)
        self.assertFalse(self.cliente._puerta_inferencia.locked())

    def test_cancelar_antes_de_conectar_no_abre_http(self):
        cancelar = Event()
        cancelar.set()
        with patch("urllib.request.urlopen") as abrir:
            with self.assertRaises(OperacionCancelada):
                self.solicitar(MagicMock(), cancelar)
            abrir.assert_not_called()
        self.assertFalse(self.cliente._puerta_inferencia.locked())

    def test_puerta_compartida_tambien_excluye_respuesta_progresiva(self):
        with self.cliente._puerta_inferencia, patch("urllib.request.urlopen") as abrir:
            with self.assertRaises(ErrorProcesamiento):
                self.solicitar(MagicMock())
            abrir.assert_not_called()
