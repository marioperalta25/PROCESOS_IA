"""Modelos de datos y entidades de dominio para el procesamiento por lotes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class EstadoProcesamiento(str, Enum):
    """Estados del ciclo de vida del proceso de inferencia masiva."""

    INACTIVO = "inactivo"
    PREPARANDO = "preparando"
    PROCESANDO = "procesando"
    PAUSADO = "pausado"
    CANCELADO = "cancelado"
    COMPLETADO = "completado"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class IdentificadorRegistro:
    """Identidad estable e inmutable de un registro de datos."""

    indice_origen: int
    clave_unica: str

    def __str__(self) -> str:
        return f"{self.indice_origen}:{self.clave_unica}"


@dataclass(frozen=True, slots=True)
class RegistroEntrada:
    """Fila leida del archivo origen con identidad y carga para inferencia."""

    identificador: str
    indice_fila: int
    valores_originales: dict[str, str]
    datos_para_modelo: dict[str, str]


@dataclass(frozen=True, slots=True)
class ResultadoEvaluacion:
    """Resultado devuelto por el modelo y verificado sintactica y semanticamente."""

    identificador: str
    es_valido_sintactico: bool
    es_valido_semantico: bool
    salida_estructurada: dict[str, Any] = field(default_factory=dict)
    errores: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class RegistroConfirmado:
    """Registro con evaluacion completada y listo para escritura final."""

    identificador: str
    indice_fila: int
    valores_finales: dict[str, str]
    marca_tiempo_utc: str


@dataclass(frozen=True, slots=True)
class TransaccionWal:
    """Lote atomico de registros preparados para confirmacion en disco."""

    numero_transaccion: int
    registros: tuple[RegistroConfirmado, ...]
    ultimo_indice_confirmado: int


@dataclass(frozen=True, slots=True)
class MetricasProgreso:
    """Métricas en tiempo real para el tablero ligero de supervisión (< 10 MB)."""

    total_estimado: int
    confirmados: int
    con_error: int
    ultimo_indice_confirmado: int
    registros_por_segundo: float
    memoria_usada_mb: float


@dataclass(frozen=True, slots=True)
class ConfiguracionTrabajo:
    """Parametros operativos inyectados; sin valores fijos en logica."""

    ruta_entrada: Path
    directorio_salida: Path
    nombre_modelo: str
    tamano_lote: int
    limite_filas_particion: int
    ventana_contexto: int
    temperatura: float
    tiempo_limite_lote_segundos: float
    columnas_evaluar: tuple[str, ...]
    prompt_sistema: str
    formato_salida: str
    columnas_salida_modelo: tuple[str, ...] = field(default_factory=tuple)
