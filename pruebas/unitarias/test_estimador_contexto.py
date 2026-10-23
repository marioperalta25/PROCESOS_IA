"""Calibración gradual, conservadora y sin retener textos de conversación."""

import unittest
from procesos_ia.aplicacion.estimador_contexto import EstimadorContexto
from procesos_ia.infraestructura.ollama.parametros_chat import cargar_parametros_chat


class PruebaEstimadorContexto(unittest.TestCase):
    def setUp(self):
        self.limites = cargar_parametros_chat()["limites"]
        self.e = EstimadorContexto(self.limites)
        self.mensajes = [{"role": "user", "content": "Texto privado sintético " * 50}]
        self.tamano = sum(len(m["content"].encode("utf-8")) for m in self.mensajes)

    def registrar(self, tokens=300, modelo="A", contexto=2048, version=None):
        self.e.registrar(modelo, contexto, self.mensajes, {"prompt_eval_count": tokens}, 1280, version)

    def test_no_relaja_por_una_muestra_y_despues_incluye_margen(self):
        inicial = self.e.coste(self.mensajes, "A", 2048)
        for _ in range(2):
            self.registrar()
            self.assertEqual(self.e.coste(self.mensajes, "A", 2048), inicial)
        self.registrar()
        ajustado = self.e.coste(self.mensajes, "A", 2048)
        self.assertLess(ajustado, inicial)
        self.assertGreaterEqual(ajustado, 300 * self.limites["calibracion_margen"])
        self.assertLessEqual(self.e.factor("A", 2048), self.limites["bytes_por_token_estimados"]
                             * (1 + self.limites["calibracion_paso_maximo"]))

    def test_no_comparte_calibracion_con_otro_modelo_o_contexto(self):
        for _ in range(5):
            self.registrar()
        self.assertNotEqual(self.e.factor("A", 2048), self.e.factor("B", 2048))
        self.assertEqual(self.e.factor("B", 2048), self.limites["bytes_por_token_estimados"])
        self.assertEqual(self.e.factor("A", 4096), self.limites["bytes_por_token_estimados"])

    def test_muestra_mas_densa_aumenta_prudencia_sin_esperar_otro_ciclo(self):
        for _ in range(5):
            self.registrar()
        anterior = self.e.factor("A", 2048)
        self.registrar(900)
        self.assertLess(self.e.factor("A", 2048), anterior)
        self.assertGreaterEqual(self.e.coste(self.mensajes, "A", 2048), 900)

    def test_ignora_datos_ausentes_invalidos_pequenos_o_cercanos_al_limite(self):
        for valor in [None, True, False, -1, 0, 1280, 2048, 300.5, "300"]:
            self.registrar(valor)
        self.e.registrar("A", 2048, [{"content": "a"}], {"prompt_eval_count": 1}, 1280)
        self.assertEqual(len(self.e._perfiles), 0)

    def test_cache_y_muestras_acotadas_sin_textos_privados(self):
        self.limites["modelos_cache"] = 2
        for _ in range(30):
            self.registrar()
        self.assertEqual(len(self.e._perfiles[("A", 2048)]["muestras"]), self.limites["calibracion_muestras"])
        self.assertNotIn("privado", str(self.e._perfiles))
        self.registrar(modelo="B")
        self.registrar(modelo="C")
        self.assertEqual(len(self.e._perfiles), 2)

    def test_invalidar_impide_reintroducir_resultados_de_version_anterior(self):
        factor, version = self.e.perfil("A", 2048)
        self.e.limpiar()
        for _ in range(5):
            self.registrar(version=version)
        self.assertEqual(self.e.factor("A", 2048), factor)
        self.assertEqual(len(self.e._perfiles), 0)
        self.assertNotEqual(self.e.perfil("A", 2048)[1], version)
