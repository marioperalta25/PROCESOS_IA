"""Validador semántico y de reglas de negocio para salidas de inferencia."""

from __future__ import annotations

from typing import Any

from procesos_ia.dominio.modelos import RegistroEntrada, ResultadoEvaluacion


class ValidadorSemantico:
    """Valida correspondencia de ID, campos obligatorios y valores admisibles."""

    def __init__(
        self,
        campos_requeridos: tuple[str, ...] = (),
        categorias_permitidas: dict[str, tuple[str, ...]] | None = None,
        verificar_identificador: bool = True,
    ) -> None:
        self._campos_requeridos = campos_requeridos
        self._categorias_permitidas = categorias_permitidas or {}
        self._verificar_id = verificar_identificador

    def validar_respuesta(
        self,
        registro_entrada: RegistroEntrada,
        respuesta_cruda: dict[str, Any],
    ) -> ResultadoEvaluacion:
        """Aplica la doble validación: sintáctica (JSON) y semántica (negocio)."""
        errores: list[str] = []

        # 1. Comprobacion de errores tecnicos, de formato o de transporte
        if not isinstance(respuesta_cruda, dict):
            return ResultadoEvaluacion(
                identificador=registro_entrada.identificador,
                es_valido_sintactico=False,
                es_valido_semantico=False,
                errores=("La respuesta recibida no es un diccionario estructurado",),
            )

        claves_error = [k for k in respuesta_cruda if k == "error" or k.startswith("error_")]
        if claves_error:
            detalles = [f"{k}: {respuesta_cruda[k]}" for k in claves_error]
            return ResultadoEvaluacion(
                identificador=registro_entrada.identificador,
                es_valido_sintactico=False,
                es_valido_semantico=False,
                errores=(f"Error reportado en respuesta: {'; '.join(detalles)}",),
            )

        # 2. Comprobacion de correspondencia de identidad
        id_devuelto = str(respuesta_cruda.get("identificador", "")).strip()
        if self._verificar_id and id_devuelto != registro_entrada.identificador:
            errores.append(
                f"Identificador devuelto '{id_devuelto}' no coincide con '{registro_entrada.identificador}'"
            )

        # 3. Comprobacion de campos requeridos
        for campo in self._campos_requeridos:
            if campo not in respuesta_cruda or str(respuesta_cruda[campo]).strip() == "":
                errores.append(f"Campo obligatorio faltante o vacio: '{campo}'")

        # 4. Comprobacion de valores en categorias permitidas
        for campo, opciones in self._categorias_permitidas.items():
            if campo in respuesta_cruda:
                valor_str = str(respuesta_cruda[campo]).strip().lower()
                opciones_normalizadas = tuple(op.strip().lower() for op in opciones)
                if valor_str not in opciones_normalizadas:
                    errores.append(
                        f"Valor '{respuesta_cruda[campo]}' no admitido para '{campo}'. Opciones: {opciones}"
                    )

        salida_limpia = {
            k: v for k, v in respuesta_cruda.items() if k != "identificador"
        }
        if not salida_limpia:
            errores.append("La respuesta no contiene campos de evaluacion estructurada")

        es_valido_semantico = len(errores) == 0

        return ResultadoEvaluacion(
            identificador=registro_entrada.identificador,
            es_valido_sintactico=True,
            es_valido_semantico=es_valido_semantico,
            salida_estructurada=salida_limpia if es_valido_semantico else {},
            errores=tuple(errores),
        )
