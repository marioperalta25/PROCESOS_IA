"""Importar avances anteriores exige evidencia del origen y de las instrucciones."""

from pathlib import Path
import tempfile
import unittest

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.comun.gestor_reanudacion_tabular import GestorReanudacionTabular
from procesos_ia.aplicacion.ia_web.comun.guardador_extracciones import (
    guardar_auditoria_modo_ia_md, guardar_filas_enriquecidas_csv,
)
from procesos_ia.aplicacion.ia_web.conversacional.formateador_lotes_chat import construir_mensaje_lote_datos
from procesos_ia.infraestructura.archivos.escritor_csv import guardar_filas_csv


class PruebaRespaldoAnterior(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)
        self.enrutador = EnrutadorSalidas(self.raiz)
        self.origen = self.raiz / "original.csv"
        self.filas = [{"nombre": "Ana", "telefono": "8322749087"}, {"nombre": "Beto", "telefono": "8328743676"}]
        guardar_filas_csv(self.filas, self.origen)
        salida = self.enrutador.reservar_salida("modo_ia", "modo_ia_original.csv")
        guardar_filas_enriquecidas_csv([
            {**self.filas[0], "_id_registro": "fila_1", "_estado_ia": "EXITOSO", "evaluacion_ia": "Guardado"},
        ], salida.ruta)
        guardar_auditoria_modo_ia_md(
            salida.ruta.with_suffix(".md"), 1, 2, 1, 1,
            construir_mensaje_lote_datos(self.filas[:1], ["nombre", "telefono"]),
            "Guardado", prompt_inicial="Evaluar",
        )
        self.anterior = salida.finalizar("cancelados")

    def preparar(self, instrucciones="Evaluar", columnas=None):
        return GestorReanudacionTabular(self.enrutador).preparar_trabajo(
            self.origen, "modo_ia", instrucciones, columnas or ["nombre", "telefono"], self.filas,
        )

    def test_recupera_anterior_verificado_y_lo_vincula_al_original(self):
        trabajo = self.preparar()
        self.assertEqual(trabajo.resumen.exitosos, 1)
        self.assertEqual(trabajo.filas[0]["telefono"], self.filas[0]["telefono"])
        with trabajo.abrir(self.enrutador, "ignorado.csv"):
            trabajo.finalizar("cancelados")
        recuperado = self.preparar()
        self.assertEqual(recuperado.resumen.pendientes, 1)
        self.assertEqual(recuperado.filas[0]["evaluacion_ia"], "Guardado")

    def test_no_importa_resultados_de_otra_plantilla_o_columnas(self):
        self.assertIsNone(self.preparar("Otra plantilla").respaldo)
        self.assertIsNone(self.preparar(columnas=["nombre"]).respaldo)

    def test_no_importa_solo_por_nombre_si_el_origen_tiene_otras_filas(self):
        self.filas[0]["nombre"] = "Otra persona"
        guardar_filas_csv(self.filas, self.origen)
        self.assertIsNone(self.preparar().respaldo)
