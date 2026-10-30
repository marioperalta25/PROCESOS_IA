"""Contratos de reserva, clasificacion y escritura compartidos entre procesos."""

import csv
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.infraestructura.archivos.escritor_csv import guardar_filas_csv


class PruebaSalidasProceso(unittest.TestCase):
    def setUp(self) -> None:
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)
        self.enrutador = EnrutadorSalidas(self.raiz)
        self.gestor = self.enrutador.gestor_procesos()

    def test_estructura_completa_en_espanol(self) -> None:
        self.enrutador.asegurar_directorios()
        for rama in ("deepseek", "gemini", "ia_local", "ia_general/imagenes", "ia_general/modo_ia"):
            for estado in ("en_proceso", "completados", "fallidos", "cancelados"):
                self.assertTrue((self.raiz / "extracciones" / rama / estado).is_dir())

    def test_archivo_original_con_igual_nombre_no_sobrescribe_salida(self) -> None:
        origen = self.raiz / "clientes.csv"
        origen.write_text("nombre\nAna\n", encoding="utf-8")
        primera = self.enrutador.reservar_salida("gemini", "clientes.csv")
        guardar_filas_csv([{"nombre": "Ana"}], primera.ruta)
        ruta_anterior = primera.finalizar()
        contenido_anterior = ruta_anterior.read_bytes()
        origen.write_text("nombre\nBeto\n", encoding="utf-8")
        segunda = self.enrutador.reservar_salida("gemini", "clientes.csv")
        tercera = self.enrutador.reservar_salida("gemini", "clientes.csv")
        self.assertEqual(segunda.ruta.name, "clientes_copia1.csv")
        self.assertEqual(tercera.ruta.name, "clientes_copia2.csv")
        self.assertEqual(ruta_anterior.read_bytes(), contenido_anterior)

    def test_reserva_vacia_tambien_ocupa_nombre(self) -> None:
        primera = self.enrutador.reservar_salida("deepseek", "datos.csv")
        segunda = self.enrutador.reservar_salida("deepseek", "datos.csv")
        self.assertFalse(primera.ruta.exists())
        self.assertEqual(segunda.ruta.name, "datos_copia1.csv")

    def test_reservas_simultaneas_no_comparten_destino(self) -> None:
        with ThreadPoolExecutor(max_workers=6) as ejecutor:
            rutas = list(ejecutor.map(
                lambda _: self.enrutador.reservar_salida("gemini", "entrada.csv").ruta,
                range(12),
            ))
        self.assertEqual(len(set(rutas)), 12)

    def test_motores_y_submodulos_no_se_cruzan(self) -> None:
        salidas = [self.enrutador.reservar_salida(modulo, "datos.csv")
                   for modulo in ("gemini", "deepseek", "ia_local", "imagenes", "modo_ia")]
        self.assertEqual(len({s.ruta for s in salidas}), 5)
        self.assertTrue(all(s.ruta.name == "datos.csv" for s in salidas))

    def test_ruta_estable_y_auditoria_junto_al_resultado(self) -> None:
        salida = self.enrutador.reservar_salida("imagenes", "fotos.csv")
        ruta_activa = salida.ruta
        auditoria = ruta_activa.with_suffix(".md")
        auditoria.write_text("Auditoria sintetica", encoding="utf-8")
        for numero in range(3):
            guardar_filas_csv([{"numero": numero}], salida.ruta)
            self.assertEqual(salida.ruta, ruta_activa)
        definitiva = salida.finalizar()
        self.assertIn("completados", definitiva.parts)
        self.assertTrue(definitiva.with_suffix(".md").exists())
        self.assertFalse(ruta_activa.exists())
        self.assertEqual(salida.finalizar(), definitiva)

    def test_fallo_conserva_archivos_y_ocupa_nombre(self) -> None:
        salida = self.enrutador.reservar_salida("modo_ia", "evaluacion.csv")
        with self.assertRaisesRegex(RuntimeError, "Fallo simulado"):
            with salida:
                guardar_filas_csv([{"dato": "parcial"}], salida.ruta)
                raise RuntimeError("Fallo simulado")
        self.assertIn("fallidos", salida.ruta.parts)
        self.assertTrue(salida.ruta.exists())
        nueva = self.enrutador.reservar_salida("modo_ia", "evaluacion.csv")
        self.assertEqual(nueva.ruta.name, "evaluacion_copia1.csv")

    def test_continuacion_explicita_conserva_nombre(self) -> None:
        salida = self.enrutador.reservar_salida("imagenes", "fotos.csv")
        guardar_filas_csv([{"dato": "parcial"}], salida.ruta)
        anterior = salida.finalizar("cancelados")
        continuacion = self.gestor.retomar("imagenes", anterior)
        self.assertIsNotNone(continuacion)
        self.assertEqual(continuacion.ruta.name, "fotos.csv")
        self.assertIn("en_proceso", continuacion.ruta.parts)
        self.assertTrue(continuacion.ruta.exists())

    def test_no_reclasifica_salida_antigua_de_otro_directorio(self) -> None:
        legado = self.raiz / "anterior.csv"
        legado.write_text("dato\nanterior\n", encoding="utf-8")
        self.assertIsNone(self.gestor.retomar("imagenes", legado))
        self.assertTrue(legado.exists())

    def test_destino_personalizado_conserva_jerarquia(self) -> None:
        personalizada = self.raiz / "elegida"
        salida = self.enrutador.reservar_salida("modo_ia", "evaluacion.csv", raiz_destino=personalizada)
        self.assertTrue(salida.ruta.is_relative_to(personalizada / "extracciones" / "ia_general" / "modo_ia"))

    def test_escritor_no_descarta_campos_posteriores_ni_transforma_telefonos(self) -> None:
        salida = self.enrutador.reservar_salida("gemini", "datos.csv")
        filas = [{"telefono": "123 / 456"}, {"telefono": "789", "motivo": "completo"}]
        guardar_filas_csv(filas, salida.ruta)
        with salida.ruta.open(encoding="utf-8-sig", newline="") as archivo:
            recuperadas = list(csv.DictReader(archivo))
        self.assertEqual(len(recuperadas), 2)
        self.assertEqual(recuperadas[0]["telefono"], "123 / 456")
        self.assertEqual(recuperadas[1]["motivo"], "completo")

    def test_rechaza_modulo_y_ruta_desconocidos(self) -> None:
        with self.assertRaises(ValueError):
            self.enrutador.reservar_salida("desconocido", "datos.csv")
        with self.assertRaises(ValueError):
            self.enrutador.reservar_salida("gemini", "../datos.csv")
