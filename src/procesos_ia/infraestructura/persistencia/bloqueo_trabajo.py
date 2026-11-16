"""Exclusion de una ejecucion por archivo; el sistema libera el bloqueo al cerrar."""

from contextlib import contextmanager
from pathlib import Path
import os
from collections.abc import Iterator


@contextmanager
def bloquear_trabajo(ruta: Path, mensaje_ocupado: str) -> Iterator[None]:
    """Impide escritores simultaneos sin dejar bloqueos activos tras un cierre brusco."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("a+b") as archivo:
        if archivo.tell() == 0:
            archivo.write(b"\0")
            archivo.flush()
        archivo.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(archivo.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(archivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError(mensaje_ocupado) from error
        try:
            yield
        finally:
            archivo.seek(0)
            if os.name == "nt":
                msvcrt.locking(archivo.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(archivo.fileno(), fcntl.LOCK_UN)
