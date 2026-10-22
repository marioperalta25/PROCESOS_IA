"""Adaptador de inferencia desacoplada que implementa ServicioInferenciaProtocol."""

from __future__ import annotations

import json
from typing import Any

from procesos_ia.aplicacion.contratos import ServicioInferenciaProtocol
from procesos_ia.dominio.modelos import ConfiguracionTrabajo, RegistroEntrada
from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.ollama.modelos import OpcionesInferencia


class ServicioInferenciaOllama:
    """Implementa ServicioInferenciaProtocol con correlación estricta por ID."""

    def __init__(self, cliente_http: ClienteHttpOllama | None = None) -> None:
        self._cliente = cliente_http or ClienteHttpOllama()

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

        respuestas: list[dict[str, Any]] = []

        for entrada in lote:
            # Filtrar estrictamente las columnas autorizadas para inferencia
            if configuracion.columnas_evaluar:
                campos_evaluar = {
                    col: entrada.datos_para_modelo[col]
                    for col in configuracion.columnas_evaluar
                    if col in entrada.datos_para_modelo
                }
                if not campos_evaluar:
                    respuestas.append(
                        {
                            "identificador": entrada.identificador,
                            "error_configuracion": (
                                "Ninguna de las columnas configuradas para evaluar "
                                f"{configuracion.columnas_evaluar} existe en el registro."
                            ),
                        }
                    )
                    continue
            else:
                campos_evaluar = entrada.datos_para_modelo

            if not campos_evaluar:
                respuestas.append(
                    {
                        "identificador": entrada.identificador,
                        "error_configuracion": "El registro no contiene datos para evaluar.",
                    }
                )
                continue

            prompt = (
                f"{configuracion.prompt_sistema}\n\n"
                f"Identificador de registro: {entrada.identificador}\n"
                f"Datos de entrada:\n{json.dumps(campos_evaluar, ensure_ascii=False)}\n\n"
                "Responde unicamente en JSON valido que incluya obligatoriamente el campo "
                f"'identificador': '{entrada.identificador}'."
            )

            try:
                salida = self._cliente.generar_estructurado(
                    modelo=configuracion.nombre_modelo,
                    prompt=prompt,
                    opciones=opciones,
                )
                # Garantizar que el identificador corresponda fielmente sin aliasing
                if isinstance(salida, dict):
                    salida_copia = dict(salida)
                    salida_copia["identificador"] = entrada.identificador
                    respuestas.append(salida_copia)
                else:
                    respuestas.append(
                        {
                            "identificador": entrada.identificador,
                            "error_formato": "La salida del modelo no es un objeto JSON",
                        }
                    )
            except Exception as error:
                # Fallo aislado en un registro: no aborta el lote completo
                respuestas.append(
                    {
                        "identificador": entrada.identificador,
                        "error_inferencia": str(error),
                    }
                )

        return respuestas

    def liberar_memoria(self, modelo: str) -> bool:
        """Descarga el modelo de la VRAM/RAM de manera forzada para cuidar el hardware."""
        return self._cliente.liberar_memoria_modelo(modelo)
