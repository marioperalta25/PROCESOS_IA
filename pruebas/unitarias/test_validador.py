"""Pruebas unitarias para el ValidadorSemantico de salidas de inferencia."""

from __future__ import annotations

import unittest

from procesos_ia.dominio.modelos import RegistroEntrada
from procesos_ia.dominio.validador import ValidadorSemantico


class PruebaValidadorSemantico(unittest.TestCase):
    def setUp(self) -> None:
        self.entrada = RegistroEntrada(
            identificador="archivo.csv:10",
            indice_fila=10,
            valores_originales={"texto": "Reclamo urgente"},
            datos_para_modelo={"texto": "Reclamo urgente"},
        )
        self.validador = ValidadorSemantico(
            campos_requeridos=("categoria", "prioridad"),
            categorias_permitidas={
                "prioridad": ("alta", "media", "baja"),
                "categoria": ("facturacion", "soporte", "ventas"),
            },
            verificar_identificador=True,
        )

    def test_validacion_exitosa(self) -> None:
        cruda = {
            "identificador": "archivo.csv:10",
            "categoria": "soporte",
            "prioridad": "alta",
        }
        res = self.validador.validar_respuesta(self.entrada, cruda)
        self.assertTrue(res.es_valido_sintactico)
        self.assertTrue(res.es_valido_semantico)
        self.assertEqual(res.salida_estructurada["categoria"], "soporte")
        self.assertEqual(res.salida_estructurada["prioridad"], "alta")

    def test_falla_por_identificador_discordante(self) -> None:
        cruda = {
            "identificador": "archivo.csv:99",
            "categoria": "soporte",
            "prioridad": "alta",
        }
        res = self.validador.validar_respuesta(self.entrada, cruda)
        self.assertTrue(res.es_valido_sintactico)
        self.assertFalse(res.es_valido_semantico)
        self.assertIn("no coincide", res.errores[0])

    def test_falla_por_campo_requerido_ausente(self) -> None:
        cruda = {
            "identificador": "archivo.csv:10",
            "prioridad": "alta",
        }
        res = self.validador.validar_respuesta(self.entrada, cruda)
        self.assertFalse(res.es_valido_semantico)
        self.assertIn("categoria", res.errores[0])

    def test_falla_por_categoria_invalida(self) -> None:
        cruda = {
            "identificador": "archivo.csv:10",
            "categoria": "soporte",
            "prioridad": "critica_extrema",  # no esta en ("alta", "media", "baja")
        }
        res = self.validador.validar_respuesta(self.entrada, cruda)
        self.assertFalse(res.es_valido_semantico)
        self.assertIn("no admitido", res.errores[0])


    def test_falla_por_error_formato_sin_campos_obligatorios(self) -> None:
        validador_vacio = ValidadorSemantico()
        cruda = {
            "identificador": "archivo.csv:10",
            "error_formato": "La salida del modelo no es un objeto JSON",
        }
        res = validador_vacio.validar_respuesta(self.entrada, cruda)
        self.assertFalse(res.es_valido_sintactico)
        self.assertFalse(res.es_valido_semantico)
        self.assertIn("error_formato", res.errores[0])

    def test_falla_por_respuesta_sin_contenido_evaluacion(self) -> None:
        validador_vacio = ValidadorSemantico()
        cruda = {"identificador": "archivo.csv:10"}
        res = validador_vacio.validar_respuesta(self.entrada, cruda)
        self.assertTrue(res.es_valido_sintactico)
        self.assertFalse(res.es_valido_semantico)
        self.assertIn("no contiene campos", res.errores[0])


if __name__ == "__main__":
    unittest.main()
