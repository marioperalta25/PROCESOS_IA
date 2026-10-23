"""Criterios reutilizables y correspondencias explicitas de un trabajo."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, TYPE_CHECKING

from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.dominio.normalizador import (
    formatear_columnas_delimitadas,
    normalizar_clave_comparacion,
)

if TYPE_CHECKING:
    from procesos_ia.dominio.prompts import PlantillaPrompt


@dataclass(frozen=True, slots=True)
class DefinicionResultado:
    """Un resultado logico no conoce encabezados de archivos concretos."""

    clave: str
    criterio: str
    entradas: tuple[str, ...] = ("datos",)
    tipo: str = "texto"
    opciones: tuple[str, ...] = ()

    def validar(self) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.clave):
            raise ErrorProcesamiento("La clave del resultado debe ser un identificador sin espacios ni tildes")
        if self.clave in {"identificador", "estado_ia", "error_ia"} or self.clave.startswith("error_"):
            raise ErrorProcesamiento("La clave del resultado esta reservada para control")
        if not self.criterio.strip() or not self.entradas or any(not e.strip() for e in self.entradas):
            raise ErrorProcesamiento("Cada resultado requiere un criterio y entradas logicas")
        if self.tipo not in ("texto", "entero", "numero", "booleano"):
            raise ErrorProcesamiento("Tipo de resultado no admitido")
        if self.opciones and self.tipo != "texto":
            raise ErrorProcesamiento("Solo los resultados de tipo texto admiten valores permitidos")
        if self.opciones:
            if len({op.casefold() for op in self.opciones}) != len(self.opciones):
                raise ErrorProcesamiento("Los valores permitidos no pueden tener duplicados")
            if any(not opcion.strip() for opcion in self.opciones):
                raise ErrorProcesamiento("Los valores permitidos no pueden estar vacios")

    def propiedad_json(self) -> dict[str, Any]:
        tipos = {"texto": "string", "entero": "integer", "numero": "number", "booleano": "boolean"}
        propiedad: dict[str, Any] = {"type": tipos[self.tipo], "description": self.criterio}
        if self.opciones:
            propiedad["enum"] = list(self.opciones)
        return propiedad

    def acepta(self, valor: Any) -> bool:
        if self.tipo == "texto":
            valido = isinstance(valor, str) and bool(valor.strip())
        elif self.tipo == "entero":
            valido = type(valor) is int
        elif self.tipo == "numero":
            try:
                valido = type(valor) in (int, float) and math.isfinite(valor)
            except OverflowError:
                valido = False
        else:
            valido = type(valor) is bool
        if not valido:
            return False
        if not self.opciones:
            return True
        if valor in self.opciones:
            return True
        if self.tipo == "texto":
            c_val = normalizar_clave_comparacion(str(valor))
            return any(normalizar_clave_comparacion(op) == c_val for op in self.opciones)
        return False

    def valor_canonico(self, valor: Any) -> Any:
        """Devuelve la opcion canonica declarada si coincide bajo normalizacion."""
        if self.tipo == "texto" and self.opciones:
            if valor in self.opciones:
                return valor
            c_val = normalizar_clave_comparacion(str(valor))
            for op in self.opciones:
                if normalizar_clave_comparacion(op) == c_val:
                    return op
        return valor


@dataclass(frozen=True, slots=True)
class VinculoEntrada:
    entrada: str
    columnas: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VinculoSalida:
    resultado: str
    columna: str


@dataclass(frozen=True, slots=True)
class ContratoEvaluacion:
    resultados: tuple[DefinicionResultado, ...]
    entradas: tuple[VinculoEntrada, ...]
    salidas: tuple[VinculoSalida, ...]

    @property
    def entradas_logicas(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(e for r in self.resultados for e in r.entradas))

    def validar(self, encabezados: tuple[str, ...] | list[str]) -> None:
        if len(set(encabezados)) != len(encabezados):
            raise ErrorProcesamiento("El archivo contiene encabezados duplicados; revise el origen antes de evaluar")
        if not self.resultados:
            raise ErrorProcesamiento("Defina al menos un resultado de evaluacion")
        for resultado in self.resultados:
            resultado.validar()
        claves = [r.clave for r in self.resultados]
        if len(set(claves)) != len(claves):
            raise ErrorProcesamiento("Hay resultados logicos duplicados")
        entradas = [e.entrada for e in self.entradas]
        salidas = [s.resultado for s in self.salidas]
        if len(set(entradas)) != len(entradas) or set(entradas) != set(self.entradas_logicas):
            raise ErrorProcesamiento("Debe vincular exactamente todas las entradas logicas")
        if len(set(salidas)) != len(salidas) or set(salidas) != set(claves):
            raise ErrorProcesamiento("Debe asignar una columna a cada resultado")
        for entrada in self.entradas:
            if not entrada.columnas or not set(entrada.columnas).issubset(encabezados):
                raise ErrorProcesamiento(f"Seleccione columnas existentes para '{entrada.entrada}'")
        destinos = [s.columna for s in self.salidas]
        if any(not c.strip() or c != c.strip() or any(ord(t) < 32 for t in c) for c in destinos):
            raise ErrorProcesamiento("Los nombres de destino no pueden estar vacios ni contener controles")
        if len({c.casefold() for c in destinos}) != len(destinos):
            raise ErrorProcesamiento("Las columnas nuevas deben tener nombres distintos")
        reservados = {"identificador", "estado_ia", "error_ia"}
        existentes = {c.casefold() for c in encabezados}
        if {c.casefold() for c in destinos} & (existentes | reservados):
            raise ErrorProcesamiento("Una columna de resultado sobrescribiria una columna original o de control")
        if existentes & {"estado_ia", "error_ia"}:
            raise ErrorProcesamiento("El origen contiene columnas reservadas de control; use otro origen")

    def esquema_json(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {r.clave: r.propiedad_json() for r in self.resultados},
            "required": [r.clave for r in self.resultados],
            "additionalProperties": False,
        }

    def preparar_datos(self, valores: dict[str, str]) -> dict[str, dict[str, str]]:
        return {e.entrada: {c: valores[c] for c in e.columnas} for e in self.entradas}

    def preparar_datos_delimitados(
        self, valores: dict[str, str], delimitador: str = " | "
    ) -> dict[str, str]:
        """Prepara entradas concatenando columnas con delimitador | para IA."""
        return {
            e.entrada: formatear_columnas_delimitadas(
                {c: valores[c] for c in e.columnas},
                columnas=e.columnas,
                delimitador=delimitador,
            )
            for e in self.entradas
        }

    def validar_salida(self, salida: dict[str, Any]) -> tuple[str, ...]:
        claves = {r.clave for r in self.resultados}
        if set(salida) != claves:
            return ("La respuesta no contiene exactamente los resultados esperados",)
        return tuple(f"Valor no admitido para '{r.clave}'" for r in self.resultados if not r.acepta(salida[r.clave]))

    def asignar_salida(self, salida: dict[str, Any]) -> dict[str, Any]:
        mapa_res = {r.clave: r for r in self.resultados}
        return {
            s.columna: (
                mapa_res[s.resultado].valor_canonico(salida[s.resultado])
                if s.resultado in mapa_res
                else salida[s.resultado]
            )
            for s in self.salidas
        }


def resultados_desde_columnas(columnas: tuple[str, ...] | list[str]) -> tuple[DefinicionResultado, ...]:
    if not isinstance(columnas, (list, tuple)) or not all(isinstance(c, str) for c in columnas):
        raise ErrorProcesamiento("Los resultados anteriores deben ser una lista de nombres")
    return tuple(DefinicionResultado(c, f"Evaluar {c}") for c in columnas)


def resultados_compatibles(plantilla: PlantillaPrompt) -> tuple[DefinicionResultado, ...]:
    """Lee plantillas previas sin reescribir sus archivos ni inventar columnas de entrada."""
    if plantilla.resultados:
        return plantilla.resultados
    return resultados_desde_columnas(plantilla.columnas_salida)


def normalizar_clave_resultado(clave: str) -> str:
    """Convierte cadenas con espacios, tildes o guiones en identificadores validos."""
    texto = clave.strip().casefold()
    reemplazos = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n"}
    for orig, dest in reemplazos.items():
        texto = texto.replace(orig, dest)
    texto = re.sub(r"[^a-z0-9_]+", "_", texto)
    texto = re.sub(r"_+", "_", texto).strip("_")
    if texto and texto[0].isdigit():
        texto = f"r_{texto}"
    return texto or clave.strip()


def resultados_desde_datos(datos: list) -> tuple[DefinicionResultado, ...]:
    """Valida el contrato compartido por persistencia, editor y refinador."""
    if not isinstance(datos, list):
        raise ErrorProcesamiento("La definicion de resultados debe ser una lista")
    resultados = []
    try:
        for dato in datos:
            if (not isinstance(dato, dict) or not isinstance(dato["entradas"], list)
                    or not isinstance(dato.get("opciones", []), list)):
                raise ValueError("Estructura de resultado invalida")
            clave = normalizar_clave_resultado(str(dato.get("clave", "")))
            tipo = str(dato.get("tipo", "texto"))
            if tipo not in ("texto", "entero", "numero", "booleano"):
                tipo = "texto"
            opciones_crudas = dato.get("opciones", [])
            if tipo == "booleano" and opciones_crudas and any(str(op).strip() for op in opciones_crudas):
                tipo = "texto"
            elif tipo != "texto":
                opciones_crudas = []
            vistas: set[str] = set()
            opciones_limpias: list[str] = []
            for op in opciones_crudas:
                texto_op = str(op).strip()
                if texto_op and texto_op.casefold() not in vistas:
                    vistas.add(texto_op.casefold())
                    opciones_limpias.append(texto_op)
            resultado = DefinicionResultado(
                clave, dato["criterio"], tuple(dato["entradas"]),
                tipo, tuple(opciones_limpias),
            )
            if not all(isinstance(c, str) for c in (
                resultado.clave, resultado.criterio, resultado.tipo,
                *resultado.entradas, *resultado.opciones,
            )):
                raise ValueError("Los metadatos del resultado deben ser texto")
            resultado.validar()
            resultados.append(resultado)
    except (KeyError, TypeError, ValueError) as error:
        raise ErrorProcesamiento("Definicion de resultados invalida") from error
    if len({r.clave for r in resultados}) != len(resultados):
        raise ErrorProcesamiento("Hay claves de resultados duplicadas")
    return tuple(resultados)
