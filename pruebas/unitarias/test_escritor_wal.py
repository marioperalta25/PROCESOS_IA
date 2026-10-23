"""Pruebas unitarias para el EscritorWal y recuperación de checkpoints."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from procesos_ia.aplicacion.coordinador import CoordinadorTrabajo
from procesos_ia.dominio.modelos import (
    ConfiguracionTrabajo,
    RegistroConfirmado,
    RegistroEntrada,
    ResultadoEvaluacion,
    TransaccionWal,
)
from procesos_ia.infraestructura.archivos.lector_csv import LectorCsv
from procesos_ia.infraestructura.persistencia.escritor_wal import EscritorWal


class FalsaInferencia:
    def procesar_lote(self, lote, config):
        return [
            {"identificador": r.identificador, "evaluacion": f"OK_{r.indice_fila}"}
            for r in lote
        ]


class FalsoValidador:
    def validar_respuesta(self, entrada, cruda):
        return ResultadoEvaluacion(
            identificador=entrada.identificador,
            es_valido_sintactico=True,
            es_valido_semantico=True,
            salida_estructurada={"evaluacion": cruda.get("evaluacion", "")},
        )


class FalsoNotificador:
    def notificar_progreso(self, metricas):
        pass

    def notificar_cambio_estado(self, estado, mensaje):
        pass


class PruebaEscritorWal(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_escritura_wal_y_confirmacion_checkpoint(self) -> None:
        escritor = EscritorWal()
        cursor = escritor.inicializar(self.raiz, ["id", "nombre", "evaluacion"])
        self.assertEqual(cursor, 0)

        r1 = RegistroConfirmado("f1", 1, {"id": "1", "nombre": "A", "evaluacion": "OK"}, "ts1")
        r2 = RegistroConfirmado("f2", 2, {"id": "2", "nombre": "B", "evaluacion": "OK"}, "ts2")

        tx = TransaccionWal(1, (r1, r2), 2)
        escritor.registrar_transaccion(tx)

        # Confirmar en disco
        confirmado = escritor.confirmar_checkpoint()
        self.assertEqual(confirmado, 2)
        escritor.cerrar()

        # Verificar reanudacion
        escritor_reanudado = EscritorWal()
        cursor_reanudado = escritor_reanudado.inicializar(
            self.raiz, ["id", "nombre", "evaluacion"]
        )
        self.assertEqual(cursor_reanudado, 2)
        escritor_reanudado.cerrar()

    def test_integracion_coordinador_con_lector_y_wal_reales(self) -> None:
        # 1. Crear CSV origen con 4 filas
        ruta_csv = self.raiz / "origen.csv"
        ruta_csv.write_text(
            "id,producto\n"
            "1,Monitor\n"
            "2,Teclado\n"
            "3,Raton\n"
            "4,Altavoces\n",
            encoding="utf-8",
        )

        dir_salida = self.raiz / "salida"

        config = ConfiguracionTrabajo(
            ruta_entrada=ruta_csv,
            directorio_salida=dir_salida,
            nombre_modelo="test-model",
            tamano_lote=2,
            limite_filas_particion=1_000_000,
            ventana_contexto=2048,
            temperatura=0.0,
            tiempo_limite_lote_segundos=10.0,
            columnas_evaluar=("producto",),
            prompt_sistema="Evaluar",
            formato_salida="csv",
            columnas_salida_modelo=("evaluacion",),
        )

        # 2. Primera ejecucion: procesar solo 1 lote de 2 filas y simular interrupcion
        lector1 = LectorCsv()
        escritor1 = EscritorWal()
        coord1 = CoordinadorTrabajo(
            lector=lector1,
            escritor_wal=escritor1,
            inferencia=FalsaInferencia(),
            validador=FalsoValidador(),
            notificador=FalsoNotificador(),
            configuracion=config,
        )

        coord1.iniciar_o_reanudar()
        coord1.procesar_siguiente_lote()
        # Estado confirmado debe ser 2
        self.assertEqual(coord1.ultimo_indice_confirmado, 2)
        coord1.cerrar()

        # 3. Segunda ejecucion: reanudar y procesar el resto
        lector2 = LectorCsv()
        escritor2 = EscritorWal()
        coord2 = CoordinadorTrabajo(
            lector=lector2,
            escritor_wal=escritor2,
            inferencia=FalsaInferencia(),
            validador=FalsoValidador(),
            notificador=FalsoNotificador(),
            configuracion=config,
        )

        cursor_reanudado = coord2.iniciar_o_reanudar()
        self.assertEqual(cursor_reanudado, 2)

        # Procesar siguiente lote (filas 3 y 4)
        hay_mas = coord2.procesar_siguiente_lote()
        self.assertTrue(hay_mas)
        self.assertEqual(coord2.ultimo_indice_confirmado, 4)

        # Fin de datos
        hay_mas = coord2.procesar_siguiente_lote()
        self.assertFalse(hay_mas)
        coord2.cerrar()

        # 4. Verificar archivo final consolidado
        archivo_resultado = dir_salida / "resultado_procesado.csv"
        lineas = archivo_resultado.read_text(encoding="utf-8").strip().splitlines()
        # Debe contener cabecera + 4 registros exactamente, sin duplicaciones
        self.assertEqual(len(lineas), 5)
        self.assertIn("Altavoces", lineas[4])

    def test_columnas_nuevas_del_modelo_llegan_al_csv(self) -> None:
        """Verifica que las columnas generadas por el LLM se escriben efectivamente en el CSV."""
        ruta_csv = self.raiz / "productos.csv"
        ruta_csv.write_text("id,item\n1,Laptop\n", encoding="utf-8")
        dir_salida = self.raiz / "salida_cols"

        config = ConfiguracionTrabajo(
            ruta_entrada=ruta_csv,
            directorio_salida=dir_salida,
            nombre_modelo="modelo-prueba",
            tamano_lote=1,
            limite_filas_particion=1_000_000,
            ventana_contexto=2048,
            temperatura=0.0,
            tiempo_limite_lote_segundos=10.0,
            columnas_evaluar=("item",),
            prompt_sistema="Evaluar",
            formato_salida="csv",
            columnas_salida_modelo=("evaluacion",),
        )

        coord = CoordinadorTrabajo(
            lector=LectorCsv(),
            escritor_wal=EscritorWal(),
            inferencia=FalsaInferencia(),
            validador=FalsoValidador(),
            notificador=FalsoNotificador(),
            configuracion=config,
        )

        coord.iniciar_o_reanudar()
        coord.procesar_siguiente_lote()
        coord.cerrar()

        archivo_resultado = dir_salida / "resultado_procesado.csv"
        lineas = archivo_resultado.read_text(encoding="utf-8").strip().splitlines()
        cabecera = lineas[0].split(",")
        self.assertIn("evaluacion", cabecera)
        self.assertIn("estado_ia", cabecera)
        self.assertIn("OK_1", lineas[1])
        self.assertIn("exito", lineas[1])

    def test_interrupcion_entre_escritura_y_checkpoint_no_duplica(self) -> None:
        """Verifica que si ocurre un corte tras escribir datos pero antes de checkpoint, no hay duplicados."""
        dir_salida = self.raiz / "salida_corte"
        escritor1 = EscritorWal()
        escritor1.inicializar(dir_salida, ["id", "texto"])

        r1 = RegistroConfirmado("f1", 1, {"id": "1", "texto": "A"}, "ts1")
        escritor1.registrar_transaccion(TransaccionWal(1, (r1,), 1))
        escritor1.confirmar_checkpoint()
        escritor1.cerrar()

        # Simular interrupcion: escribir manualmente r2 al CSV sin haber actualizado el checkpoint
        ruta_csv = dir_salida / "resultado_procesado.csv"
        with open(ruta_csv, "a", encoding="utf-8") as f:
            f.write("2,B_incompleto\n")

        # Reanudar con escritor2: debe detectar que el checkpoint confirmado fue solo 1
        # y truncar el archivo eliminando los bytes no confirmados
        escritor2 = EscritorWal()
        cursor = escritor2.inicializar(dir_salida, ["id", "texto"])
        self.assertEqual(cursor, 1)

        # Ahora registrar transaccion 2 completa y confirmar
        r2_real = RegistroConfirmado("f2", 2, {"id": "2", "texto": "B_real"}, "ts2")
        escritor2.registrar_transaccion(TransaccionWal(2, (r2_real,), 2))
        escritor2.confirmar_checkpoint()
        escritor2.cerrar()

        lineas = ruta_csv.read_text(encoding="utf-8").strip().splitlines()
        # Debe tener: cabecera, registro 1 y registro 2 (sin duplicar ni conservar el incompleto)
        self.assertEqual(len(lineas), 3)
        self.assertIn("B_real", lineas[2])
        self.assertNotIn("B_incompleto", ruta_csv.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
