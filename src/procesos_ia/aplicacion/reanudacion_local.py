"""Busqueda de respaldos compatibles: politica exclusiva del procesamiento local."""

from dataclasses import dataclass
import json
from pathlib import Path
import re

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.rutas_salida import sanitizar_nombre_subcarpeta
from procesos_ia.dominio.modelos import ConfiguracionTrabajo
from procesos_ia.infraestructura.persistencia.identidad_trabajo import IdentidadTrabajo


@dataclass(frozen=True)
class ContinuacionLocal:
    directorio: Path
    nombre_archivo: str
    confirmados: int


def buscar_continuacion_local(
    configuracion: ConfiguracionTrabajo, enrutador: EnrutadorSalidas, raiz: Path,
) -> ContinuacionLocal | None:
    """Busca sin escribir; exige la identidad persistida del origen y la evaluacion."""
    gestor = enrutador.gestor_procesos(raiz)
    rama = gestor.rama("ia_local")
    nombre = sanitizar_nombre_subcarpeta(configuracion.ruta_entrada.stem)
    carpetas = {configuracion.directorio_salida}
    for estado in ("en_proceso", "cancelados", "fallidos"):
        base = rama / gestor.configuracion["estados"][estado]
        if base.is_dir():
            carpetas.update(c for c in base.iterdir() if c.is_dir())
    # Compatibilidad con salidas locales previas a la organizacion por estados.
    for base in (Path(raiz) / enrutador.analisis.name, Path(raiz)):
        if base.is_dir():
            carpetas.update(c for c in base.glob(f"{nombre}_*") if c.is_dir())
    candidatas = [c for c in carpetas if c.is_dir() and (c / "progreso.checkpoint").is_file()]
    if not candidatas:
        return None
    identidad = IdentidadTrabajo(configuracion)
    copia = re.escape(gestor.configuracion["sufijo_copia"]).replace(re.escape("{numero}"), r"[0-9]+")
    patron = re.compile(r"resultado_procesado(?:" + copia + r")?\.csv", re.IGNORECASE)
    for carpeta in sorted(candidatas, key=lambda c: c.stat().st_mtime_ns, reverse=True):
        if (carpeta / "completado.json").exists():
            continue
        try:
            anterior = json.loads((carpeta / "identidad_trabajo.json").read_text(encoding="utf-8"))
            progreso = json.loads((carpeta / "progreso.checkpoint").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(anterior, dict) or anterior.get("huella") != identidad.huella:
            continue
        if not isinstance(progreso, dict):
            continue
        confirmados = progreso.get("ultimo_indice_confirmado")
        if type(confirmados) is not int or confirmados < 0:
            continue
        archivos = [a for a in carpeta.iterdir() if a.is_file() and patron.fullmatch(a.name)]
        if len(archivos) == 1:
            return ContinuacionLocal(carpeta, archivos[0].name, confirmados)
    return None
