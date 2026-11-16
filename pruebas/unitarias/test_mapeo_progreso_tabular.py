"""Una respuesta ambigua no debe confirmar otra fila ni introducir IDs del modelo."""

import unittest

from procesos_ia.aplicacion.ia_web.conversacional.procesador_modo_ia import mapear_respuestas_lote


class PruebaMapeoProgresoTabular(unittest.TestCase):
    def setUp(self):
        self.lote = [{"_id_registro": "fila_20"}, {"_id_registro": "fila_21"}]

    def test_resultados_fuera_de_orden_respetan_la_fila_cero(self):
        datos = [{"id": 2, "evaluacion_ia": "Segundo"}, {"id": 1, "evaluacion_ia": "Primero"}]
        filas = mapear_respuestas_lote("", datos, self.lote)
        self.assertEqual([f["evaluacion_ia"] for f in filas], ["Primero", "Segundo"])
        self.assertEqual([f["_id_registro"] for f in filas], ["fila_20", "fila_21"])

    def test_json_sin_fila_correspondiente_no_se_usa_como_texto_exitoso(self):
        datos = {"resultados": [{"id": 99, "evaluacion_ia": "Ajeno"}]}
        filas = mapear_respuestas_lote('{"resultados": [{"id":99}]}', datos, self.lote)
        self.assertTrue(all(f["_estado_ia"] == "OMITIDO" for f in filas))

    def test_json_con_resultados_vacios_no_confirma_filas(self):
        filas = mapear_respuestas_lote('{"resultados": []}', {"resultados": []}, self.lote)
        self.assertTrue(all(f["_estado_ia"] == "OMITIDO" for f in filas))

    def test_ids_repetidos_se_rechazan(self):
        with self.assertRaises(ValueError):
            mapear_respuestas_lote("", [{"id": 1, "valor": "A"}, {"id": 1, "valor": "B"}], self.lote)

    def test_respuesta_parcial_conserva_la_fila_omitida(self):
        filas = mapear_respuestas_lote("", [{"id": 2, "calificacion": "A"}], self.lote)
        self.assertEqual([f["_estado_ia"] for f in filas], ["OMITIDO", "EXITOSO"])
        self.assertNotIn("calificacion", filas[0])

    def test_identificadores_invalidos_no_se_sustituyen_por_la_posicion(self):
        for identificador in (0, True, "ajeno"):
            with self.subTest(identificador=identificador):
                filas = mapear_respuestas_lote("", [{"id": identificador, "valor": "A"}], self.lote)
                self.assertTrue(all(f["_estado_ia"] == "OMITIDO" for f in filas))

    def test_etiqueta_ajena_no_se_reinterpreta_por_orden(self):
        filas = mapear_respuestas_lote("[FILA 99]: Ajeno", {}, self.lote)
        self.assertTrue(all(f["_estado_ia"] == "OMITIDO" for f in filas))
