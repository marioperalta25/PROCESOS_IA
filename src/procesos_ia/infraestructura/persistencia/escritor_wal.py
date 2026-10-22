"""Escritor atomico y bitacora WAL para recuperacion de progreso confirmado."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import TextIO

from procesos_ia.dominio.excepciones import ErrorIntegridadWal, ErrorProcesamiento
from procesos_ia.dominio.modelos import RegistroConfirmado, TransaccionWal


class EscritorWal:
    """Implementa EscritorWalProtocol con bitácora fsync y checkpoints atómicos."""

    def __init__(
        self,
        nombre_archivo_wal: str = "transacciones.wal",
        nombre_checkpoint: str = "progreso.checkpoint",
        nombre_consolidado: str = "resultado_procesado.csv",
        limite_filas_particion: int = 1_000_000,
    ) -> None:
        self._nombre_wal = nombre_archivo_wal
        self._nombre_checkpoint = nombre_checkpoint
        self._nombre_consolidado = nombre_consolidado
        self._limite_particion = limite_filas_particion

        self._directorio: Path | None = None
        self._encabezados: list[str] = []
        self._ultimo_confirmado = 0
        self._filas_en_particion_actual = 0
        self._numero_particion = 1

        self._manejador_wal: TextIO | None = None
        self._manejador_consolidado: TextIO | None = None
        self._escritor_csv: csv.DictWriter | None = None
        self._transaccion_pendiente: TransaccionWal | None = None

    @property
    def ultimo_confirmado(self) -> int:
        return self._ultimo_confirmado

    def inicializar(self, directorio_base: Path, encabezados: list[str]) -> int:
        """Prepara el directorio, recupera checkpoint previo o inicializa salidas."""
        self._directorio = directorio_base
        self._directorio.mkdir(parents=True, exist_ok=True)
        self._encabezados = list(encabezados)

        ruta_checkpoint = self._directorio / self._nombre_checkpoint
        bytes_confirmados: int | None = None
        if ruta_checkpoint.is_file():
            datos_cp = self._leer_checkpoint(ruta_checkpoint)
            self._ultimo_confirmado = int(datos_cp.get("ultimo_indice_confirmado", 0))
            bytes_confirmados = datos_cp.get("bytes_consolidado")
            # Restaurar encabezados consolidados si existian previamente
            if "encabezados" in datos_cp and isinstance(datos_cp["encabezados"], list):
                for col in datos_cp["encabezados"]:
                    if col not in self._encabezados:
                        self._encabezados.append(col)
        else:
            self._ultimo_confirmado = 0

        # Abrir archivo WAL para agregado
        ruta_wal = self._directorio / self._nombre_wal
        self._manejador_wal = open(ruta_wal, "a", encoding="utf-8")

        # Preparar consolidado reconciliando contra el ultimo checkpoint confirmado
        self._abrir_consolidado(bytes_confirmados)
        return self._ultimo_confirmado

    def registrar_transaccion(self, transaccion: TransaccionWal) -> None:
        """Escribe la transaccion en el WAL y asegura su persistencia física con fsync."""
        if self._manejador_wal is None:
            raise ErrorProcesamiento("El escritor WAL no ha sido inicializado")

        linea_wal = json.dumps(
            {
                "tx": transaccion.numero_transaccion,
                "ultimo_indice": transaccion.ultimo_indice_confirmado,
                "total_registros": len(transaccion.registros),
                "registros": [
                    {
                        "id": r.identificador,
                        "fila": r.indice_fila,
                        "valores": r.valores_finales,
                        "ts": r.marca_tiempo_utc,
                    }
                    for r in transaccion.registros
                ],
            },
            ensure_ascii=False,
        )

        self._manejador_wal.write(linea_wal + "\n")
        self._manejador_wal.flush()
        os.fsync(self._manejador_wal.fileno())

        self._transaccion_pendiente = transaccion

    def confirmar_checkpoint(self) -> int:
        """Vuelca transaccion al archivo consolidado y actualiza checkpoint atomico."""
        if self._transaccion_pendiente is None:
            return self._ultimo_confirmado

        if (
            self._manejador_consolidado is None
            or self._escritor_csv is None
            or self._directorio is None
        ):
            raise ErrorProcesamiento("Manejador consolidado no disponible")

        # Particionado si excede limite de filas
        if self._filas_en_particion_actual >= self._limite_particion:
            self._rotar_particion()

        # Escribir filas al archivo final
        for registro in self._transaccion_pendiente.registros:
            fila = {col: registro.valores_finales.get(col, "") for col in self._encabezados}
            self._escritor_csv.writerow(fila)
            self._filas_en_particion_actual += 1

        self._manejador_consolidado.flush()
        os.fsync(self._manejador_consolidado.fileno())

        bytes_confirmados = self._manejador_consolidado.tell()
        nuevo_indice = self._transaccion_pendiente.ultimo_indice_confirmado
        self._guardar_checkpoint_atomico(nuevo_indice, bytes_confirmados)

        self._ultimo_confirmado = nuevo_indice
        self._transaccion_pendiente = None
        return self._ultimo_confirmado

    def recuperar_ultimo_progreso(self) -> int:
        return self._ultimo_confirmado

    def cerrar(self) -> None:
        """Cierra descriptores abiertos garantizando vaciado."""
        if self._manejador_wal is not None and not self._manejador_wal.closed:
            self._manejador_wal.flush()
            self._manejador_wal.close()
        if (
            self._manejador_consolidado is not None
            and not self._manejador_consolidado.closed
        ):
            self._manejador_consolidado.flush()
            self._manejador_consolidado.close()

    def _abrir_consolidado(self, bytes_confirmados: int | None = None) -> None:
        if self._directorio is None:
            return

        ruta_consolidado = self._ruta_particion_actual()
        existe = ruta_consolidado.is_file() and ruta_consolidado.stat().st_size > 0

        # Si el progreso confirmado es 0, descartar restos no confirmados de intentos previos
        if self._ultimo_confirmado == 0:
            self._manejador_consolidado = open(
                ruta_consolidado, "w", encoding="utf-8", newline=""
            )
            self._escritor_csv = csv.DictWriter(
                self._manejador_consolidado, fieldnames=self._encabezados
            )
            self._escritor_csv.writeheader()
            self._manejador_consolidado.flush()
            os.fsync(self._manejador_consolidado.fileno())
            return

        # Si estamos reanudando y hay un offset de bytes confirmado por checkpoint
        if existe:
            if bytes_confirmados is not None:
                tamano_actual = ruta_consolidado.stat().st_size
                if tamano_actual > bytes_confirmados:
                    # Truncar datos sobrantes de una caida antes de guardar checkpoint
                    with open(ruta_consolidado, "r+b") as f_trunc:
                        f_trunc.seek(bytes_confirmados)
                        f_trunc.truncate()

            self._manejador_consolidado = open(
                ruta_consolidado, "a", encoding="utf-8", newline=""
            )
            self._escritor_csv = csv.DictWriter(
                self._manejador_consolidado, fieldnames=self._encabezados
            )
        else:
            self._manejador_consolidado = open(
                ruta_consolidado, "w", encoding="utf-8", newline=""
            )
            self._escritor_csv = csv.DictWriter(
                self._manejador_consolidado, fieldnames=self._encabezados
            )
            self._escritor_csv.writeheader()
            self._manejador_consolidado.flush()
            os.fsync(self._manejador_consolidado.fileno())

    def _rotar_particion(self) -> None:
        if self._manejador_consolidado is not None:
            self._manejador_consolidado.flush()
            self._manejador_consolidado.close()

        self._numero_particion += 1
        self._filas_en_particion_actual = 0
        self._abrir_consolidado()

    def _ruta_particion_actual(self) -> Path:
        assert self._directorio is not None
        if self._numero_particion == 1:
            return self._directorio / self._nombre_consolidado

        nombre_base = Path(self._nombre_consolidado).stem
        sufijo = Path(self._nombre_consolidado).suffix
        nombre_part = f"{nombre_base}_parte{self._numero_particion}{sufijo}"
        return self._directorio / nombre_part

    def _leer_checkpoint(self, ruta: Path) -> dict[str, Any]:
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            if not isinstance(datos, dict):
                raise ValueError("El contenido del checkpoint no es un diccionario")
            return datos
        except (json.JSONDecodeError, ValueError) as error:
            raise ErrorIntegridadWal(f"Archivo de checkpoint corrupto: {error}")

    def _guardar_checkpoint_atomico(
        self, nuevo_indice: int, bytes_confirmados: int
    ) -> None:
        assert self._directorio is not None
        ruta_final = self._directorio / self._nombre_checkpoint
        ruta_tmp = self._directorio / f"{self._nombre_checkpoint}.tmp"

        contenido = json.dumps(
            {
                "ultimo_indice_confirmado": nuevo_indice,
                "bytes_consolidado": bytes_confirmados,
                "particion_actual": self._numero_particion,
                "filas_particion": self._filas_en_particion_actual,
                "encabezados": self._encabezados,
            },
            ensure_ascii=False,
            indent=2,
        )
        ruta_tmp.write_text(contenido, encoding="utf-8")

        # Renombrado atomico en sistema de archivos (reemplaza destino limpiamente)
        ruta_tmp.replace(ruta_final)
