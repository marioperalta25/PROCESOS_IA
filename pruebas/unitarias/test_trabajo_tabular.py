"""Recuperacion real de copias, identidad, aislamiento y errores de persistencia."""

import csv
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

from procesos_ia.aplicacion.comun.gestor_reanudacion_base import (
    COLUMNA_ESTADO, COLUMNA_ID, GestorReanudacionBase,
)
from procesos_ia.aplicacion.comun.trabajo_tabular import leer_progreso
from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.comun.gestor_reanudacion_tabular import GestorReanudacionTabular
from procesos_ia.dominio.reanudacion import AccionReanudacion
from procesos_ia.dominio.excepciones import ErrorPersistenciaTabular
from procesos_ia.infraestructura.archivos.escritor_csv import guardar_filas_csv


class PruebaTrabajoTabular(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)
        self.enrutador = EnrutadorSalidas(self.raiz / "salidas")
        self.origen = self.raiz / "entrada.csv"
        self.filas = [{"nombre": f"Registro {i}", "estado": "OK" if i < 6 else "CA"} for i in range(3639)]
        guardar_filas_csv(self.filas, self.origen)
        self.original = self.origen.read_bytes()

    def preparar(self, instrucciones="Evaluar", columnas=None, modulo="modo_ia", opciones=None):
        return GestorReanudacionTabular(self.enrutador).preparar_trabajo(
            self.origen, modulo, instrucciones, columnas or ["nombre"], self.filas, opciones,
        )

    def guardar_cancelado(self, cantidad=528):
        trabajo = self.preparar()
        with trabajo.abrir(self.enrutador, "resultado.csv"):
            trabajo.confirmar([
                {**fila, COLUMNA_ESTADO: "EXITOSO", "evaluacion_ia": f"Resultado {i}"}
                for i, fila in enumerate(trabajo.filas_pendientes[:cantidad])
            ])
            ruta = trabajo.finalizar("cancelados")
        return ruta

    def test_estado_geografico_no_es_progreso(self):
        _, resumen = GestorReanudacionBase.inspeccionar_csv(self.origen)
        self.assertEqual((resumen.exitosos, resumen.pendientes), (0, 3639))
        self.assertFalse(resumen.requiere_decision)

    def test_recuperar_528_desde_original_tras_recrear_enrutador(self):
        ruta = self.guardar_cancelado()
        self.enrutador = EnrutadorSalidas(self.enrutador.raiz)
        trabajo = self.preparar()
        self.assertEqual((trabajo.resumen.total, trabajo.resumen.exitosos, trabajo.resumen.pendientes), (3639, 528, 3111))
        self.assertEqual(trabajo.filas_pendientes[0][COLUMNA_ID], "fila_529")
        self.assertEqual(trabajo.filas[0]["evaluacion_ia"], "Resultado 0")
        self.assertEqual(trabajo.respaldo.parent.parent, ruta.parent)
        self.assertEqual(self.origen.read_bytes(), self.original)

    def test_copia_completa_existe_antes_de_la_primera_consulta(self):
        trabajo = self.preparar()
        with trabajo.abrir(self.enrutador, "resultado.csv") as salida:
            ruta_prog = salida.directorio / trabajo.parametros["carpeta_estado"] / trabajo.parametros["archivo_progreso"]
            filas = leer_progreso(ruta_prog, trabajo.parametros)
            self.assertEqual(len(filas), 3639)
            self.assertTrue(all(f[COLUMNA_ESTADO] == "PENDIENTE" for f in filas))
            trabajo.finalizar("cancelados")

    def test_otras_instrucciones_columnas_motor_hoja_y_archivo_no_reutilizan(self):
        self.guardar_cancelado()
        for cambios in ({"instrucciones": "Otra plantilla"}, {"columnas": ["estado"]},
                        {"modulo": "gemini"}, {"opciones": {"hoja": "Otra"}}):
            with self.subTest(cambios=cambios):
                self.assertIsNone(self.preparar(**cambios).respaldo)
        otro = self.raiz / "otro" / self.origen.name
        otro.parent.mkdir()
        otro.write_bytes(self.original)
        self.origen = otro
        self.assertIsNone(self.preparar().respaldo)

    def test_continuar_preserva_exitos_y_fallidos_no_seleccionados(self):
        self.filas = self.filas[:3]
        guardar_filas_csv(self.filas, self.origen)
        trabajo = self.preparar()
        with trabajo.abrir(self.enrutador, "resultado.csv"):
            trabajo.confirmar([
                {**trabajo.filas[0], COLUMNA_ESTADO: "EXITOSO", "evaluacion_ia": "Anterior"},
                {**trabajo.filas[1], COLUMNA_ESTADO: "FALLIDO"},
            ])
            trabajo.finalizar("cancelados")
        trabajo = self.preparar()
        trabajo.seleccionar(AccionReanudacion.SOLO_PENDIENTES)
        self.assertEqual([f[COLUMNA_ID] for f in trabajo.filas_pendientes], ["fila_3"])
        with trabajo.abrir(self.enrutador, "ignorado.csv"):
            trabajo.confirmar([{**trabajo.filas_pendientes[0], COLUMNA_ESTADO: "EXITOSO"}])
            salida = trabajo.finalizar("completados")
        self.assertIn("fallidos", salida.parts)
        recuperado = self.preparar()
        self.assertEqual(recuperado.filas[0]["evaluacion_ia"], "Anterior")
        self.assertEqual([f[COLUMNA_ID] for f in recuperado.filas_pendientes], ["fila_2"])

    def test_reiniciar_crea_otra_copia_y_la_memoria_prefiere_la_nueva(self):
        anterior = self.guardar_cancelado()
        contenido = anterior.read_bytes()
        trabajo = self.preparar()
        trabajo.seleccionar(AccionReanudacion.REINICIAR_TODO)
        with trabajo.abrir(self.enrutador, "resultado.csv"):
            nueva = trabajo.finalizar("cancelados")
        self.assertNotEqual(anterior, nueva)
        self.assertEqual(anterior.read_bytes(), contenido)
        recuperado = self.preparar()
        self.assertEqual(recuperado.resumen.exitosos, 0)
        self.assertTrue(recuperado.resumen.requiere_decision)

    def test_respaldo_faltante_o_truncado_no_inicia_desde_cero(self):
        self.guardar_cancelado()
        trabajo = self.preparar()
        contenido = trabajo.respaldo.read_bytes()
        trabajo.respaldo.unlink()
        with self.assertRaises(FileNotFoundError):
            self.preparar()
        trabajo.respaldo.write_bytes(contenido.splitlines(keepends=True)[0])
        with self.assertRaises(ValueError):
            self.preparar()

    def test_identificadores_duplicados_no_sobrescriben(self):
        trabajo = self.preparar()
        with trabajo.abrir(self.enrutador, "resultado.csv"):
            with self.assertRaises(ValueError):
                trabajo.confirmar([trabajo.filas[0], trabajo.filas[0]])
            trabajo.finalizar("cancelados")
        self.assertEqual(self.preparar().resumen.exitosos, 0)

    def test_fallo_de_escritura_no_confirma_avance(self):
        trabajo = self.preparar()
        with self.assertRaises(ErrorPersistenciaTabular):
            with trabajo.abrir(self.enrutador, "resultado.csv"):
                with patch("procesos_ia.aplicacion.comun.trabajo_tabular.guardar_filas_csv", side_effect=OSError("Disco lleno")):
                    trabajo.confirmar([{**trabajo.filas[0], COLUMNA_ESTADO: "EXITOSO"}])
        self.assertEqual(trabajo.resumen.exitosos, 0)
        self.assertEqual(self.preparar().resumen.exitosos, 0)

    def test_cambio_de_origen_despues_de_preparar_detiene_sin_reservar(self):
        trabajo = self.preparar()
        self.origen.write_text("otro contenido", encoding="utf-8")
        with self.assertRaises(ValueError):
            with trabajo.abrir(self.enrutador, "resultado.csv"):
                self.fail("No debe iniciar")
        self.assertFalse(self.enrutador.gestor_procesos().rama("modo_ia").exists())

    def test_no_permite_dos_escritores_y_el_bloqueo_se_libera(self):
        primero, segundo = self.preparar(), self.preparar()
        with primero.abrir(self.enrutador, "resultado.csv"):
            with self.assertRaises(RuntimeError):
                with segundo.abrir(self.enrutador, "resultado.csv"):
                    self.fail("No debe abrir otro escritor")
            primero.finalizar("cancelados")
        recuperado = self.preparar()
        with recuperado.abrir(self.enrutador, "resultado.csv"):
            recuperado.finalizar("cancelados")

    def test_progreso_cambiado_tras_dialogo_no_se_sobrescribe(self):
        self.guardar_cancelado()
        antiguo = self.preparar()
        reciente = self.preparar()
        with reciente.abrir(self.enrutador, "resultado.csv"):
            reciente.confirmar([{**reciente.filas_pendientes[0], COLUMNA_ESTADO: "EXITOSO"}])
            reciente.finalizar("cancelados")
        with self.assertRaises(ValueError):
            with antiguo.abrir(self.enrutador, "resultado.csv"):
                self.fail("No debe reemplazar progreso mas reciente")
        self.assertEqual(self.preparar().resumen.exitosos, 529)

    def test_cierre_brusco_conserva_el_lote_y_libera_el_bloqueo(self):
        programa = '''
import csv, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[3])
from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.comun.gestor_reanudacion_tabular import GestorReanudacionTabular
origen, raiz = Path(sys.argv[1]), Path(sys.argv[2])
with origen.open(encoding="utf-8-sig", newline="") as archivo:
    filas = list(csv.DictReader(archivo))
enrutador = EnrutadorSalidas(raiz)
trabajo = GestorReanudacionTabular(enrutador).preparar_trabajo(origen, "modo_ia", "Evaluar", ["nombre"], filas)
with trabajo.abrir(enrutador, "resultado.csv"):
    trabajo.confirmar([{**trabajo.filas[0], "_estado_ia": "EXITOSO", "evaluacion_ia": "Confirmado"}])
    os._exit(0)
'''
        fuente = Path(__file__).resolve().parents[2] / "src"
        subprocess.run([sys.executable, "-B", "-c", programa, str(self.origen), str(self.enrutador.raiz), str(fuente)], check=True, timeout=20)
        trabajo = self.preparar()
        self.assertEqual(trabajo.resumen.exitosos, 1)
        with trabajo.abrir(self.enrutador, "resultado.csv"):
            salida = trabajo.finalizar("cancelados")
        self.assertTrue(salida.exists())

    def test_identidad_corrupta_no_se_ignora(self):
        self.guardar_cancelado()
        trabajo = self.preparar()
        ruta = trabajo.respaldo.parent / trabajo.parametros["archivo_identidad"]
        ruta.write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.preparar()

    def test_ids_de_negocio_repetidos_conservan_filas_independientes(self):
        self.filas = [{"id_registro": "cliente", "nombre": "Ana"}, {"id_registro": "cliente", "nombre": "Beto"}]
        guardar_filas_csv(self.filas, self.origen)
        trabajo = self.preparar()
        self.assertEqual([f[COLUMNA_ID] for f in trabajo.filas], ["fila_1", "fila_2"])
