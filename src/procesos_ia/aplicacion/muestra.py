"""Vista previa acotada que reutiliza inferencia y validacion sin escribir resultados."""

from dataclasses import dataclass, field
from threading import Event

from procesos_ia.aplicacion.contratos import LectorFlujoProtocol, ServicioInferenciaProtocol
from procesos_ia.dominio.modelos import ConfiguracionTrabajo, ResultadoEvaluacion
from procesos_ia.dominio.validador import ValidadorSemantico
from procesos_ia.dominio.excepciones import ErrorProcesamiento


@dataclass(frozen=True, slots=True)
class FilaMuestra:
    indice: int
    datos_evaluados: dict[str, str]
    evaluacion: ResultadoEvaluacion
    originales: dict[str, str] = field(default_factory=dict)


def evaluar_muestra(
    configuracion: ConfiguracionTrabajo, lector: LectorFlujoProtocol,
    inferencia: ServicioInferenciaProtocol, limite: int, cancelacion: Event,
) -> list[FilaMuestra]:
    if limite <= 0:
        raise ErrorProcesamiento("El limite de la muestra debe ser positivo")
    configuracion.validar_esquema_salida()
    contrato = configuracion.obtener_contrato()
    validador = ValidadorSemantico(contrato=contrato)
    filas = []
    try:
        encabezados = lector.inicializar(configuracion.ruta_entrada)
        contrato.validar(encabezados)
        for entrada in lector.leer_bloque(limite, 0):
            if cancelacion.is_set():
                break
            respuestas = inferencia.procesar_lote([entrada], configuracion)
            respuesta = respuestas[0] if len(respuestas) == 1 else {}
            resultado = validador.validar_respuesta(entrada, respuesta)
            columnas_evaluadas = {
                col: entrada.valores_originales[col]
                for vinculo in contrato.entradas
                for col in vinculo.columnas
                if col in entrada.valores_originales
            }
            filas.append(FilaMuestra(
                indice=entrada.indice_fila,
                datos_evaluados=columnas_evaluadas,
                evaluacion=resultado,
                originales=dict(entrada.valores_originales),
            ))
        return filas
    finally:
        lector.cerrar()
