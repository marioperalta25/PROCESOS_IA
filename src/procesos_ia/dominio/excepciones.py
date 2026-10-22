"""Excepciones de dominio para el procesamiento de datos e inferencia local."""

from __future__ import annotations


class ErrorProcesamiento(Exception):
    """Excepcion base para fallos durante el procesamiento de datos."""


class ErrorValidacionSemantica(ErrorProcesamiento):
    """Indica que una respuesta del modelo no cumple las reglas de negocio."""

    def __init__(self, identificador: str, motivo: str) -> None:
        self.identificador = identificador
        self.motivo = motivo
        super().__init__(f"Fallo semantico en registro '{identificador}': {motivo}")


class ErrorIntegridadWal(ErrorProcesamiento):
    """Indica discrepancia o fallo de consistencia en el registro WAL."""

    def __init__(self, detalle: str) -> None:
        self.detalle = detalle
        super().__init__(f"Error de integridad en bitacora WAL: {detalle}")


class ErrorRecuperacionProgreso(ErrorProcesamiento):
    """Indica imposibilidad de reconciliar el cursor con el progreso confirmado."""

    def __init__(self, ultimo_confirmado: int, causa: str) -> None:
        self.ultimo_confirmado = ultimo_confirmado
        self.causa = causa
        super().__init__(
            f"No se pudo recuperar desde el indice {ultimo_confirmado}: {causa}"
        )
