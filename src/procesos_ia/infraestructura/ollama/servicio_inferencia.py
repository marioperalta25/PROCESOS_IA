"""Adaptador de inferencia desacoplada que implementa ServicioInferenciaProtocol."""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any

from procesos_ia.aplicacion.contratos import ServicioInferenciaProtocol
from procesos_ia.dominio.modelos import ConfiguracionTrabajo, RegistroEntrada
from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.ollama.modelos import OpcionesInferencia
from procesos_ia.infraestructura.prompts.parametros import cargar_parametros_evaluacion


class ServicioInferenciaOllama:
    """Implementa ServicioInferenciaProtocol con correlación estricta por ID."""

    def __init__(self, cliente_http: ClienteHttpOllama | None = None) -> None:
        self._cliente = cliente_http or ClienteHttpOllama()
        self._instruccion = cargar_parametros_evaluacion()["instruccion_ejecucion"]

    def procesar_lote(
        self,
        lote: list[RegistroEntrada],
        configuracion: ConfiguracionTrabajo,
    ) -> list[dict[str, Any]]:
        """Procesa registros del lote asegurando que cada salida porte su ID original."""
        opciones = OpcionesInferencia(
            temperatura=configuracion.temperatura,
            num_ctx=configuracion.ventana_contexto,
            tiempo_limite_segundos=configuracion.tiempo_limite_lote_segundos,
        )

        contrato = configuracion.obtener_contrato()
        configuracion.validar_esquema_salida()
        esquema = contrato.esquema_json()
        evaluaciones = [asdict(r) for r in contrato.resultados]
        respuestas: list[dict[str, Any]] = []
        for entrada in lote:
            try:
                datos = contrato.preparar_datos_delimitados(entrada.datos_para_modelo)
            except KeyError:
                respuestas.append({
                    "identificador": entrada.identificador,
                    "error_configuracion": "Faltan columnas de entrada vinculadas; no se envio el registro",
                })
                continue
            prompt = (
                f"### CRITERIOS Y REGLAS DE EVALUACION:\n{configuracion.prompt_sistema}\n\n"
                f"### EVALUACIONES REQUERIDAS:\n{json.dumps(evaluaciones, ensure_ascii=False, indent=2)}\n\n"
                f"### DATOS DE ENTRADA A EVALUAR:\n{json.dumps(datos, ensure_ascii=False, indent=2)}\n\n"
                f"### ESQUEMA JSON DE RESPUESTA REQUERIDO:\n{json.dumps(esquema, ensure_ascii=False, indent=2)}\n"
            )
            try:
                salida = self._cliente.generar_estructurado(
                    modelo=configuracion.nombre_modelo, prompt=prompt,
                    esquema_salida=esquema, opciones=opciones, sistema=self._instruccion,
                )
                errores = contrato.validar_salida(salida) if isinstance(salida, dict) else ("La salida no es un objeto JSON",)
                if errores:
                    respuestas.append({
                        "identificador": entrada.identificador,
                        "error_formato": "; ".join(errores),
                    })
                else:
                    # La identidad pertenece a la peticion Python, nunca al texto del modelo.
                    respuestas.append({"identificador": entrada.identificador, **salida})
            except Exception as error:
                respuestas.append({
                    "identificador": entrada.identificador, "error_inferencia": str(error),
                })
        return respuestas

    def liberar_memoria(self, modelo: str) -> bool:
        """Descarga el modelo de la VRAM/RAM de manera forzada para cuidar el hardware."""
        return self._cliente.liberar_memoria_modelo(modelo)
