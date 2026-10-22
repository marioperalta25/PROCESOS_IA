"""Motor de refinamiento asistido que convierte ideas del usuario en prompts estructurados."""

from __future__ import annotations

import json
from typing import Any

from procesos_ia.dominio.excepciones import ErrorProcesamiento
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
        prompt_completo = (
            f"{self._metaprompt}\n\n"
            f"Intencion del usuario:\n{peticion.idea_usuario}\n\n"
            f"Columnas del archivo origen: {list(peticion.columnas_entrada)}\n"
            f"Ejemplo de fila:\n{json.dumps(peticion.ejemplo_fila, ensure_ascii=False)}\n\n"
            "Genera la respuesta estrictamente en JSON con los campos: "
            "'prompt_refinado', 'columnas_salida' y 'explicacion'."
        )

        opciones = OpcionesInferencia(
            temperatura=0.2,
            num_ctx=2048,
            tiempo_limite_segundos=60.0,
        )

        try:
            salida = self._cliente.generar_estructurado(
                modelo=nombre_modelo,
                prompt=prompt_completo,
                opciones=opciones,
            )
        except Exception as error:
            raise ErrorProcesamiento(f"Fallo al conectar con Ollama para refinamiento: {error}")

        if not isinstance(salida, dict) or "prompt_refinado" not in salida:
            raise ErrorProcesamiento("El modelo no devolvio el formato de refinamiento esperado")

        columnas_raw = salida.get("columnas_salida", [])
        if isinstance(columnas_raw, list):
            columnas_salida = tuple(str(c).strip() for c in columnas_raw if str(c).strip())
        else:
            columnas_salida = ()

        return ResultadoRefinamiento(
            prompt_refinado=str(salida.get("prompt_refinado", "")).strip(),
            columnas_salida_sugeridas=columnas_salida,
            explicacion_resumen=str(salida.get("explicacion", "")).strip(),
        )

    @staticmethod
    def _metaprompt_predeterminado() -> str:
        return (
            "Eres un ingeniero experto en diseno de prompts para modelos de lenguaje locales. "
            "Tu tarea es convertir la intencion informal del usuario en una instruccion de sistema "
            "optimizada, clara y concisa para procesar filas de datos.\n"
            "Reglas de diseno obligatorias:\n"
            "1. La instruccion debe exigir al modelo responder unicamente en formato JSON estricto.\n"
            "2. Debe instruir que nunca incluya comentarios, introducciones ni bloques explicativos fuera del JSON.\n"
            "3. Debe exigir que incluya obligatoriamente el campo 'identificador' correspondiente a cada registro.\n"
            "4. Define nombres de columnas de salida breves y en espanol (ej. categoria, calificacion, resumen)."
        )
