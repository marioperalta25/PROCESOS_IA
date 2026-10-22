"""Lector de flujos por bloques para archivos CSV y TXT conforme a RFC 4180."""

from __future__ import annotations

from collections.abc import Iterator
import csv
from pathlib import Path

from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.dominio.modelos import RegistroEntrada
from procesos_ia.infraestructura.archivos.detector_formato import (
    detectar_codificacion,
    detectar_delimitador,
    detectar_encabezados,
)


class LectorCsv:
    """Implementa LectorFlujoProtocol para archivos de texto delimitado."""

    def __init__(
        self,
        codificacion_forzada: str | None = None,
        delimitador_forzado: str | None = None,
    ) -> None:
        self._codificacion_forzada = codificacion_forzada
        self._delimitador_forzado = delimitador_forzado

        self._ruta: Path | None = None
        self._codificacion: str = "utf-8"
        self._delimitador: str = ","
        self._encabezados: list[str] = []
        self._filas_saltar_cabecera: int = 0
        self._total_estimado: int | None = None
        self._manejador_flujo: Any | None = None
        self._lector_flujo: Any | None = None
        self._contador_flujo: int = 0

    @property
    def encabezados(self) -> list[str]:
        return list(self._encabezados)

    @property
    def codificacion(self) -> str:
        return self._codificacion

    @property
    def delimitador(self) -> str:
        return self._delimitador

    def inicializar(self, ruta_archivo: Path) -> list[str]:
        """Detecta codificacion, delimitador y encabezados con muestreo acotado."""
        if not ruta_archivo.is_file():
            raise ErrorProcesamiento(f"El archivo no existe: {ruta_archivo}")

        self._ruta = ruta_archivo
        self._codificacion = self._codificacion_forzada or detectar_codificacion(
            ruta_archivo
        )
        self._delimitador = self._delimitador_forzado or detectar_delimitador(
            ruta_archivo, self._codificacion
        )

        filas_muestra: list[list[str]] = []
        with open(
            self._ruta, "r", encoding=self._codificacion, errors="replace", newline=""
        ) as f:
            lector = csv.reader(f, delimiter=self._delimitador)
            for _ in range(5):
                try:
                    filas_muestra.append(next(lector))
                except StopIteration:
                    break

        inspeccion = detectar_encabezados(filas_muestra)
        if inspeccion.tiene_encabezado:
            self._encabezados = inspeccion.encabezados
            self._filas_saltar_cabecera = inspeccion.indice_fila_encabezado + 1
        else:
            self._encabezados = inspeccion.encabezados
            self._filas_saltar_cabecera = inspeccion.indice_fila_encabezado

        return list(self._encabezados)

    def abrir_flujo(self, saltar_hasta_indice: int) -> None:
        """Abre el archivo una sola vez y avanza el cursor al punto de reanudacion."""
        if self._ruta is None:
            raise ErrorProcesamiento("El lector no ha sido inicializado")

        self.cerrar()
        self._manejador_flujo = open(
            self._ruta, "r", encoding=self._codificacion, errors="replace", newline=""
        )
        self._lector_flujo = csv.reader(self._manejador_flujo, delimiter=self._delimitador)

        # Saltar cabeceras
        for _ in range(self._filas_saltar_cabecera):
            try:
                next(self._lector_flujo)
            except StopIteration:
                return

        # Saltar hasta el cursor confirmado
        self._contador_flujo = 0
        while self._contador_flujo < saltar_hasta_indice:
            try:
                fila = next(self._lector_flujo)
                if any(celda.strip() for celda in fila):
                    self._contador_flujo += 1
            except StopIteration:
                break

    def leer_siguiente_bloque(self, tamano_bloque: int) -> list[RegistroEntrada]:
        """Extrae el siguiente bloque desde el flujo abierto en tiempo O(1) por fila."""
        if self._lector_flujo is None or self._ruta is None:
            raise ErrorProcesamiento("El flujo no esta abierto; llame a abrir_flujo()")

        nombre_archivo = self._ruta.name
        registros: list[RegistroEntrada] = []

        while len(registros) < tamano_bloque:
            try:
                fila = next(self._lector_flujo)
            except StopIteration:
                break

            if not any(celda.strip() for celda in fila):
                continue

            self._contador_flujo += 1
            valores_originales: dict[str, str] = {}
            for idx, nombre_col in enumerate(self._encabezados):
                val = fila[idx] if idx < len(fila) else ""
                valores_originales[nombre_col] = val

            identificador = f"{nombre_archivo}:{self._contador_flujo}"
            registros.append(
                RegistroEntrada(
                    identificador=identificador,
                    indice_fila=self._contador_flujo,
                    valores_originales=valores_originales,
                    datos_para_modelo=dict(valores_originales),
                )
            )

        return registros

    def leer_bloque(
        self,
        tamano_bloque: int,
        saltar_hasta_indice: int,
    ) -> Iterator[RegistroEntrada]:
        """Genera registros mapeados estrictamente por identificador desde el cursor."""
        if self._ruta is None:
            raise ErrorProcesamiento("El lector no ha sido inicializado")

        nombre_archivo = self._ruta.name
        contador_registro = 0
        emitidos = 0

        with open(
            self._ruta, "r", encoding=self._codificacion, errors="replace", newline=""
        ) as f:
            lector = csv.reader(f, delimiter=self._delimitador)

            # Omitir filas previas al inicio de los datos (ej. cabeceras o lineas vacias)
            for _ in range(self._filas_saltar_cabecera):
                try:
                    next(lector)
                except StopIteration:
                    return

            for fila in lector:
                # Omitir filas completamente vacias
                if not any(celda.strip() for celda in fila):
                    continue

                contador_registro += 1
                if contador_registro <= saltar_hasta_indice:
                    continue

                # Normalizacion estructural de campos
                valores_originales: dict[str, str] = {}
                for idx, nombre_col in enumerate(self._encabezados):
                    val = fila[idx] if idx < len(fila) else ""
                    valores_originales[nombre_col] = val

                identificador = f"{nombre_archivo}:{contador_registro}"
                yield RegistroEntrada(
                    identificador=identificador,
                    indice_fila=contador_registro,
                    valores_originales=valores_originales,
                    datos_para_modelo=dict(valores_originales),
                )

                emitidos += 1
                if emitidos >= tamano_bloque:
                    break

    def estimar_total_registros(self) -> int:
        """Conteo rapido de filas sin retener contenido en memoria RAM."""
        if self._ruta is None:
            return 0
        if self._total_estimado is not None:
            return self._total_estimado

        total = 0
        with open(
            self._ruta, "r", encoding=self._codificacion, errors="replace", newline=""
        ) as f:
            lector = csv.reader(f, delimiter=self._delimitador)
            for _ in range(self._filas_saltar_cabecera):
                try:
                    next(lector)
                except StopIteration:
                    break
            for fila in lector:
                if any(c.strip() for c in fila):
                    total += 1

        self._total_estimado = total
        return total

    def cerrar(self) -> None:
        """Libera descriptores de archivo y referencias locales."""
        if self._manejador_flujo is not None and not self._manejador_flujo.closed:
            self._manejador_flujo.close()
        self._manejador_flujo = None
        self._lector_flujo = None
        self._total_estimado = None
