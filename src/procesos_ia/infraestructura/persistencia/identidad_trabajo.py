"""Impide reanudar salidas con otro origen, plantilla o correspondencia."""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.dominio.modelos import ConfiguracionTrabajo


class IdentidadTrabajo:
    def __init__(self, configuracion: ConfiguracionTrabajo) -> None:
        self.origen = configuracion.ruta_entrada.resolve()
        self._marca = self._marca_origen()
        contrato = asdict(configuracion)
        contrato.pop("directorio_salida")
        contrato["ruta_entrada"] = str(self.origen)
        contrato["marca_origen"] = self._marca
        serializado = json.dumps(contrato, sort_keys=True, ensure_ascii=False, default=str)
        self.huella = hashlib.sha256(serializado.encode("utf-8")).hexdigest()

    def _marca_origen(self) -> tuple[int, int, int]:
        estado = self.origen.stat()
        return estado.st_size, estado.st_mtime_ns, estado.st_ino

    def verificar_origen(self) -> None:
        if self._marca_origen() != self._marca:
            raise ErrorProcesamiento("El archivo origen cambio durante el trabajo; se detuvo la escritura")

    def vincular(self, directorio: Path, existe_progreso: bool) -> None:
        ruta = directorio / "identidad_trabajo.json"
        if ruta.exists():
            try:
                datos = json.loads(ruta.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise ErrorProcesamiento("No se pudo verificar la identidad del trabajo anterior") from error
            if not isinstance(datos, dict) or datos.get("huella") != self.huella:
                raise ErrorProcesamiento("La salida pertenece a otro trabajo o configuracion; elija otra carpeta")
        elif existe_progreso:
            raise ErrorProcesamiento("La salida anterior no tiene identidad verificable; elija otra carpeta")
        else:
            temporal = ruta.with_suffix(".tmp")
            temporal.write_text(json.dumps({"huella": self.huella}), encoding="utf-8")
            temporal.replace(ruta)
