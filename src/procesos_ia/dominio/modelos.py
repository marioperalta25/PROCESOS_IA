"""Modelos de datos y entidades de dominio para el procesamiento por lotes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.dominio.evaluaciones import (
    ContratoEvaluacion, VinculoEntrada, VinculoSalida, resultados_desde_columnas,
)


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
    contrato_evaluacion: ContratoEvaluacion | None = None
    identificador_plantilla: str = ""
    version_plantilla: int = 0
    carpeta_imagenes: Path | None = None
    rotacion_chat_cada: int = 1
    modo_procesamiento: str = "lote"

    def obtener_contrato(self) -> ContratoEvaluacion:
        """Adapta configuraciones anteriores a un contrato explicito."""
        if self.contrato_evaluacion is not None:
            return self.contrato_evaluacion
        return ContratoEvaluacion(
            resultados_desde_columnas(self.columnas_salida_modelo),
            (VinculoEntrada("datos", self.columnas_evaluar),),
            tuple(VinculoSalida(c, c) for c in self.columnas_salida_modelo),
        )

    def validar_esquema_salida(self) -> None:
        """Exige columnas explicitas para no descartar resultados silenciosamente."""
        columnas = self.columnas_salida_modelo
        if not columnas or any(not columna.strip() for columna in columnas):
            raise ErrorProcesamiento("Indique al menos una columna de salida del modelo")
        if len(set(columnas)) != len(columnas):
            raise ErrorProcesamiento("Las columnas de salida no pueden estar duplicadas")
        if set(columnas) & {"identificador", "estado_ia", "error_ia"}:
            raise ErrorProcesamiento("Las columnas de salida usan nombres reservados de control")
        contrato = self.obtener_contrato()
        if tuple(s.columna for s in contrato.salidas) != columnas:
            raise ErrorProcesamiento("Las columnas de salida no coinciden con el contrato")
        contrato.validar(self.columnas_evaluar)
