"""Pruebas unitarias para el CoordinadorTrabajo y persistencia de progreso."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any
import unittest

from procesos_ia.aplicacion.coordinador import CoordinadorTrabajo
from procesos_ia.dominio.modelos import (
    ConfiguracionTrabajo,
    EstadoProcesamiento,
    MetricasProgreso,
    RegistroEntrada,
    ResultadoEvaluacion,
    TransaccionWal,
)


class FalsoLector:
    def __init__(self, registros: list[RegistroEntrada]) -> None:
        self._registros = registros
        self.cerrado = False
        self._cursor = 0

    def inicializar(self, ruta_archivo: Path) -> list[str]:
        return ["id", "texto", "categoria"]

    def abrir_flujo(self, saltar_hasta_indice: int) -> None:
        self._cursor = saltar_hasta_indice

    def leer_siguiente_bloque(self, tamano_bloque: int) -> list[RegistroEntrada]:
        filtrados = [r for r in self._registros if r.indice_fila > self._cursor]
        lote = filtrados[:tamano_bloque]
        if lote:
            self._cursor = lote[-1].indice_fila
        return lote

    def leer_bloque(
        self, tamano_bloque: int, saltar_hasta_indice: int
    ) -> Iterator[RegistroEntrada]:
        filtrados = [r for r in self._registros if r.indice_fila > saltar_hasta_indice]
        return iter(filtrados[:tamano_bloque])

    def estimar_total_registros(self) -> int:
        return len(self._registros)

    def cerrar(self) -> None:
        self.cerrado = True


class FalsoEscritorWal:
    def __init__(self, ultimo_previo: int = 0) -> None:
        self._ultimo_confirmado = ultimo_previo
        self.transacciones: list[TransaccionWal] = []
        self.checkpoints_llamados = 0
        self.cerrado = False

    def vincular_trabajo(self, configuracion: ConfiguracionTrabajo) -> None:
        self.configuracion = configuracion

    def inicializar(self, directorio_base: Path, encabezados: list[str]) -> int:
        return self._ultimo_confirmado

    def registrar_transaccion(self, transaccion: TransaccionWal) -> None:
        self.transacciones.append(transaccion)

    def confirmar_checkpoint(self) -> int:
        self.checkpoints_llamados += 1
        if self.transacciones:
            self._ultimo_confirmado = self.transacciones[-1].ultimo_indice_confirmado
        return self._ultimo_confirmado

    def recuperar_ultimo_progreso(self) -> int:
        return self._ultimo_confirmado

    def cerrar(self) -> None:
        self.cerrado = True


class FalsoServicioInferencia:
    def __init__(self, alterar_orden: bool = False) -> None:
        self.alterar_orden = alterar_orden

    def procesar_lote(
        self,
        lote: list[RegistroEntrada],
        configuracion: ConfiguracionTrabajo,
    ) -> list[dict[str, Any]]:
        respuestas = [
            {"identificador": reg.identificador, "clasificacion": "A"}
            for reg in lote
        ]
        if self.alterar_orden:
            respuestas.reverse()
        return respuestas


class FalsoValidador:
    def validar_respuesta(
        self,
        registro_entrada: RegistroEntrada,
        respuesta_cruda: dict[str, Any],
    ) -> ResultadoEvaluacion:
        identificador = respuesta_cruda.get("identificador", "")
        if identificador != registro_entrada.identificador:
            return ResultadoEvaluacion(
                identificador=registro_entrada.identificador,
                es_valido_sintactico=False,
                es_valido_semantico=False,
                errores=("Identificador discordante",),
            )
        return ResultadoEvaluacion(
            identificador=identificador,
            es_valido_sintactico=True,
            es_valido_semantico=True,
            salida_estructurada={"clasificacion": respuesta_cruda.get("clasificacion")},
        )


class FalsoNotificador:
    def __init__(self) -> None:
        self.metricas: list[MetricasProgreso] = []
        self.estados: list[EstadoProcesamiento] = []

    def notificar_progreso(self, metricas: MetricasProgreso) -> None:
        self.metricas.append(metricas)

    def notificar_cambio_estado(
        self, estado: EstadoProcesamiento, mensaje: str
    ) -> None:
        self.estados.append(estado)


class PruebaCoordinador(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ConfiguracionTrabajo(
            ruta_entrada=Path("entrada.csv"),
            directorio_salida=Path("salida/"),
            nombre_modelo="qwen2.5:1.5b",
            tamano_lote=2,
            limite_filas_particion=1_000_000,
            ventana_contexto=2048,
            temperatura=0.1,
            tiempo_limite_lote_segundos=30.0,
            columnas_evaluar=("texto",),
            prompt_sistema="Clasifica el texto.",
            formato_salida="csv",
            columnas_salida_modelo=("clasificacion",),
        )
        self.registros = [
            RegistroEntrada("r1", 1, {"id": "1", "texto": "a"}, {"texto": "a"}),
            RegistroEntrada("r2", 2, {"id": "2", "texto": "b"}, {"texto": "b"}),
            RegistroEntrada("r3", 3, {"id": "3", "texto": "c"}, {"texto": "c"}),
        ]

    def test_iniciar_reanudacion_desde_wal(self) -> None:
        lector = FalsoLector(self.registros)
        escritor = FalsoEscritorWal(ultimo_previo=2)
        coordinador = CoordinadorTrabajo(
            lector=lector,
            escritor_wal=escritor,
            inferencia=FalsoServicioInferencia(),
            validador=FalsoValidador(),
            notificador=FalsoNotificador(),
            configuracion=self.config,
        )

        ultimo = coordinador.iniciar_o_reanudar()
        self.assertEqual(ultimo, 2)
        self.assertEqual(coordinador.estado, EstadoProcesamiento.PROCESANDO)

    def test_correspondencia_por_identificador_y_commit_wal(self) -> None:
        lector = FalsoLector(self.registros)
        escritor = FalsoEscritorWal(ultimo_previo=0)
        # La inferencia altera el orden deliberadamente para verificar robustez
        inferencia = FalsoServicioInferencia(alterar_orden=True)
        validador = FalsoValidador()
        notificador = FalsoNotificador()

        coordinador = CoordinadorTrabajo(
            lector=lector,
            escritor_wal=escritor,
            inferencia=inferencia,
            validador=validador,
            notificador=notificador,
            configuracion=self.config,
        )

        coordinador.iniciar_o_reanudar()
        avanzo = coordinador.procesar_siguiente_lote()

        self.assertTrue(avanzo)
        self.assertEqual(coordinador.ultimo_indice_confirmado, 2)
        self.assertEqual(escritor.checkpoints_llamados, 1)
        self.assertEqual(len(escritor.transacciones), 1)

        tx = escritor.transacciones[0]
        # Verificar que r1 y r2 quedaron correctamente emparejados a pesar del orden inverso
        ids_confirmados = [r.identificador for r in tx.registros]
        self.assertEqual(ids_confirmados, ["r1", "r2"])

    def test_respuesta_invalida_se_persiste_como_error_sin_dejar_hueco(self) -> None:
        """Comprueba que si r1 falla y r2 triunfa, r1 no se descarta ni se salta."""
        lector = FalsoLector(self.registros)
        escritor = FalsoEscritorWal(ultimo_previo=0)

        # Inferencia devuelve solo r2 (falta r1 deliberadamente)
        class InferenciaFaltante:
            def procesar_lote(self, lote, config):
                return [{"identificador": "r2", "clasificacion": "A"}]

        validador = FalsoValidador()
        notificador = FalsoNotificador()

        coordinador = CoordinadorTrabajo(
            lector=lector,
            escritor_wal=escritor,
            inferencia=InferenciaFaltante(),
            validador=validador,
            notificador=notificador,
            configuracion=self.config,
        )

        coordinador.iniciar_o_reanudar()
        avanzo = coordinador.procesar_siguiente_lote()

        self.assertTrue(avanzo)
        self.assertEqual(coordinador.ultimo_indice_confirmado, 2)
        self.assertEqual(len(escritor.transacciones), 1)

        tx = escritor.transacciones[0]
        # Ambos registros deben estar en la transaccion WAL
        self.assertEqual(len(tx.registros), 2)
        r1_guardado = tx.registros[0]
        r2_guardado = tx.registros[1]

        self.assertEqual(r1_guardado.identificador, "r1")
        self.assertEqual(r1_guardado.valores_finales["estado_ia"], "error")
        self.assertIn("Identificador discordante", r1_guardado.valores_finales["error_ia"])

        self.assertEqual(r2_guardado.identificador, "r2")
        self.assertEqual(r2_guardado.valores_finales["estado_ia"], "exito")

    def test_metrica_memoria_real_distinta_de_cero(self) -> None:
        """Comprueba que la telemetria de memoria mide el consumo real del proceso."""
        lector = FalsoLector(self.registros)
        escritor = FalsoEscritorWal()
        notificador = FalsoNotificador()

        coordinador = CoordinadorTrabajo(
            lector=lector,
            escritor_wal=escritor,
            inferencia=FalsoServicioInferencia(),
            validador=FalsoValidador(),
            notificador=notificador,
            configuracion=self.config,
        )

        coordinador.iniciar_o_reanudar()
        coordinador.procesar_siguiente_lote()

        self.assertTrue(len(notificador.metricas) > 0)
        ultima_metrica = notificador.metricas[-1]
        self.assertGreater(ultima_metrica.memoria_usada_mb, 0.0)


if __name__ == "__main__":
    unittest.main()
