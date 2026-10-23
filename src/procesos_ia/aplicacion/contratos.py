"""Contratos e interfaces tipadas para adaptadores e infraestructura."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol

from procesos_ia.dominio.modelos import (
    ConfiguracionTrabajo,
    EstadoProcesamiento,
    MetricasProgreso,
    RegistroConfirmado,
    RegistroEntrada,
    ResultadoEvaluacion,
    TransaccionWal,
)


class LectorFlujoProtocol(Protocol):
    """Contrato para lectura por bloques de archivos masivos sin saturar RAM."""

    def inicializar(self, ruta_archivo: Path) -> list[str]:
        """Abre el archivo, valida estructura y retorna los encabezados detectados."""
        ...

    def abrir_flujo(self, saltar_hasta_indice: int) -> None:
        """Abre el descriptor continuo y posiciona el cursor sin recorrer en cada lote."""
        ...

    def leer_siguiente_bloque(self, tamano_bloque: int) -> list[RegistroEntrada]:
        """Extrae el siguiente bloque desde el flujo abierto en tiempo O(1) por fila."""
        ...

    def leer_bloque(
        self,
        tamano_bloque: int,
        saltar_hasta_indice: int,
    ) -> Iterator[RegistroEntrada]:
        """Genera registros mapeados con identidad estable a partir de un indice."""
        ...

    def estimar_total_registros(self) -> int:
        """Calcula o estima el numero total de filas a procesar."""
        ...

    def cerrar(self) -> None:
        """Libera manejadores de archivo y descriptores de lectura."""
        ...


class EscritorWalProtocol(Protocol):
    """Contrato para persistencia segura en disco basada en Write-Ahead Log."""

    def vincular_trabajo(self, configuracion: ConfiguracionTrabajo) -> None:
        """Establece la identidad del origen y contrato antes de recuperar progreso."""
        ...

    def inicializar(self, directorio_base: Path, encabezados: list[str]) -> int:
        """Prepara bitacora WAL y devuelve el ultimo indice confirmado previo."""
        ...

    def registrar_transaccion(self, transaccion: TransaccionWal) -> None:
        """Escribe un lote de registros pendientes en la bitacora de cambios."""
        ...

    def confirmar_checkpoint(self) -> int:
        """Sincroniza en disco (fsync) y actualiza el puntero de progreso confirmado."""
        ...

    def recuperar_ultimo_progreso(self) -> int:
        """Consulta el indice del ultimo registro consolidado y libre de fallos."""
        ...

    def cerrar(self) -> None:
        """Cierra archivos temporales y consolida registros pendientes."""
        ...


class ServicioInferenciaProtocol(Protocol):
    """Contrato para comunicación con el motor local de Ollama."""

    def procesar_lote(
        self,
        lote: list[RegistroEntrada],
        configuracion: ConfiguracionTrabajo,
    ) -> list[dict[str, Any]]:
        """Envia lote a Ollama con esquema estructurado y retorna salidas crudas."""
        ...


class ValidadorSemanticoProtocol(Protocol):
    """Contrato para validacion sintactica y reglas de negocio del resultado."""

    def validar_respuesta(
        self,
        registro_entrada: RegistroEntrada,
        respuesta_cruda: dict[str, Any],
    ) -> ResultadoEvaluacion:
        """Valida correspondencia de ID, campos requeridos y valores permitidos."""
        ...


class NotificadorProgresoProtocol(Protocol):
    """Contrato para telemetría ligera hacia la interfaz gráfica (< 10 MB)."""

    def notificar_progreso(self, metricas: MetricasProgreso) -> None:
        """Emite métricas cuantitativas hacia el tablero en tiempo real."""
        ...

    def notificar_cambio_estado(
        self,
        estado: EstadoProcesamiento,
        mensaje: str,
    ) -> None:
        """Informa transiciones de estado de la tarea en curso."""
        ...
