"""Motor de refinamiento asistido que convierte ideas del usuario en prompts estructurados."""

from __future__ import annotations

import json
from typing import Any

from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.dominio.evaluaciones import resultados_desde_columnas, resultados_desde_datos
from procesos_ia.infraestructura.prompts.parametros import cargar_parametros_evaluacion
from procesos_ia.dominio.prompts import (
    PeticionRefinamiento,
    ResultadoRefinamiento,
)
from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.ollama.modelos import OpcionesInferencia


class RefinadorPromptOllama:
    """Implementa MotorRefinamientoProtocol usando inferencia estructurada de Ollama."""

    def __init__(
        self,
        cliente_http: ClienteHttpOllama,
        metaprompt_base: str | None = None,
    ) -> None:
        self._cliente = cliente_http
        self._metaprompt = metaprompt_base or self._metaprompt_predeterminado()

    def refinar_prompt(
        self,
        peticion: PeticionRefinamiento,
        nombre_modelo: str,
    ) -> ResultadoRefinamiento:
        """Invoca al LLM local para transformar la intención en una plantilla robusta."""
        prompt_completo = json.dumps({"intencion": peticion.idea_usuario}, ensure_ascii=False)
        texto = {"type": "string"}
        lista_texto = {"type": "array", "items": texto}
        esquema = {
            "type": "object", "additionalProperties": False,
            "required": ["prompt_refinado", "resultados", "explicacion"],
            "properties": {
                "prompt_refinado": texto, "explicacion": texto,
                "resultados": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["clave", "criterio", "entradas", "tipo", "opciones"],
                    "properties": {
                        "clave": texto, "criterio": texto,
                        "entradas": {**lista_texto, "minItems": 1},
                        "tipo": {"type": "string", "enum": ["texto", "entero", "numero", "booleano"]},
                        "opciones": lista_texto,
                    },
                }},
            },
        }

        parametros = cargar_parametros_evaluacion()
        tiempo_limite = float(parametros.get("tiempo_limite_refinamiento_segundos", 90.0))
        opciones = OpcionesInferencia(
            temperatura=0.2,
            num_ctx=2048,
            tiempo_limite_segundos=tiempo_limite,
        )

        try:
            salida = self._cliente.generar_estructurado(
                modelo=nombre_modelo,
                prompt=prompt_completo,
                opciones=opciones,
                sistema=self._metaprompt, esquema_salida=esquema,
            )
        except Exception as error:
            raise ErrorProcesamiento(f"Fallo al conectar con Ollama para refinamiento: {error}")

        if not isinstance(salida, dict) or "prompt_refinado" not in salida:
            raise ErrorProcesamiento("El modelo no devolvio el formato de refinamiento esperado")

        if "resultados" in salida:
            resultados = resultados_desde_datos(salida["resultados"])
        else:
            # Adaptacion de respuestas de refinadores anteriores, sin reescribir plantillas.
            columnas = salida.get("columnas_salida", [])
            resultados = resultados_desde_columnas(columnas)
        if not resultados or not str(salida["prompt_refinado"]).strip():
            raise ErrorProcesamiento("El refinador no definio criterios y resultados utilizables")

        return ResultadoRefinamiento(
            prompt_refinado=str(salida["prompt_refinado"]).strip(),
            columnas_salida_sugeridas=tuple(r.clave for r in resultados),
            explicacion_resumen=str(salida.get("explicacion", "")).strip(),
            resultados=resultados,
        )

    @staticmethod
    def _metaprompt_predeterminado() -> str:
        return cargar_parametros_evaluacion()["instruccion_refinamiento"]
