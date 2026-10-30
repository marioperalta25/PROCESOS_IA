"""Reserva y organizacion comun de salidas, sin interpretar resultados de negocio."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

from procesos_ia.aplicacion.rutas_salida import sanitizar_nombre_subcarpeta


def cargar_configuracion_salidas(ruta: Path | None = None) -> dict:
    """Lee y valida las ramas y estados declarativos sin crear directorios."""
    archivo = ruta or (Path(__file__).resolve().parents[3]
                       / "recursos" / "configuracion" / "salidas.toml")
    datos = tomllib.loads(archivo.read_text(encoding="utf-8"))
    segmentos = [datos["carpeta_padre"], datos["carpeta_reservas"]]
    segmentos.extend(datos["estados"].values())
    for rama in datos["modulos"].values():
        if not isinstance(rama, list) or not rama:
            raise ValueError("Cada modulo debe declarar una rama de salida")
        segmentos.extend(rama)
    if any(not isinstance(s, str) or not s or s in (".", "..")
           or Path(s).name != s or any(c in s for c in '/\\:*?"<>|')
           for s in segmentos):
        raise ValueError("Las carpetas de salida deben ser nombres simples")
    if set(datos["estados"]) != {"en_proceso", "completados", "fallidos", "cancelados"}:
        raise ValueError("La configuracion no contiene los estados de salida requeridos")
    if len(set(datos["estados"].values())) != len(datos["estados"]):
        raise ValueError("Las carpetas de estado deben ser diferentes")
    sufijo = datos["sufijo_copia"]
    try:
        ejemplo = "salida" + sufijo.format(numero=1)
    except (KeyError, ValueError, AttributeError) as error:
        raise ValueError("El sufijo de copia tiene un formato invalido") from error
    if "{numero}" not in sufijo or sanitizar_nombre_subcarpeta(ejemplo) != ejemplo:
        raise ValueError("El sufijo de copia debe contener {numero} y ser un nombre valido")
    return datos


@dataclass
class SalidaProceso:
    """Una reserva conserva su ruta hasta que el consumidor termina de escribir."""

    rama: Path
    directorio: Path
    nombre_archivo: str
    configuracion: dict
    estado: str = "en_proceso"

    @property
    def ruta(self) -> Path:
        return self.directorio / self.nombre_archivo

    def finalizar(self, estado: str = "completados") -> Path:
        """Clasifica la carpeta completa una vez cerrados sus archivos."""
        carpeta_estado = self.configuracion["estados"].get(estado)
        if carpeta_estado is None:
            raise ValueError(f"Estado de salida desconocido: {estado}")
        if self.estado == estado:
            return self.ruta
        destino = self.rama / carpeta_estado / self.directorio.name
        if not self.directorio.resolve().is_relative_to(self.rama.resolve()):
            raise ValueError("La salida no pertenece a la rama del proceso")
        if destino.exists():
            raise FileExistsError(f"El destino ya esta ocupado: {destino}")
        destino.parent.mkdir(parents=True, exist_ok=True)
        self.directorio.rename(destino)
        self.directorio = destino
        self.estado = estado
        return self.ruta

    def __enter__(self) -> SalidaProceso:
        return self

    def __exit__(self, tipo, error, traza) -> None:
        if error is not None and self.estado == "en_proceso":
            try:
                self.finalizar("fallidos")
                error.add_note(f"Los archivos del trabajo se conservan en {self.directorio}")
            except OSError as fallo:
                error.add_note(f"La salida se conserva en {self.directorio}: {fallo}")


class GestorSalidasProceso:
    """Aplica la misma reserva de nombres a cualquier modulo registrado."""

    def __init__(self, raiz: Path, configuracion: dict | None = None) -> None:
        self.raiz = Path(raiz)
        self.configuracion = configuracion or cargar_configuracion_salidas()

    def rama(self, modulo: str) -> Path:
        segmentos = self.configuracion["modulos"].get(modulo)
        if segmentos is None:
            raise ValueError(f"Modulo de salida desconocido: {modulo}")
        return self.raiz / self.configuracion["carpeta_padre"] / Path(*segmentos)

    def asegurar_directorios(self) -> None:
        for modulo in self.configuracion["modulos"]:
            for carpeta in self.configuracion["estados"].values():
                (self.rama(modulo) / carpeta).mkdir(parents=True, exist_ok=True)

    def retomar(self, modulo: str, ruta: Path) -> SalidaProceso | None:
        """Conserva una ruta expresamente elegida por la logica de continuacion."""
        rama = self.rama(modulo).resolve()
        archivo = Path(ruta).resolve()
        for estado, carpeta in self.configuracion["estados"].items():
            if archivo.parent.parent == rama / carpeta:
                salida = SalidaProceso(rama, archivo.parent, archivo.name, self.configuracion, estado)
                salida.finalizar("en_proceso")
                return salida
        # Los resultados antiguos siguen bajo el control de su consumidor.
        return None

    def reservar(
        self, modulo: str, nombre_archivo: str, nombre_trabajo: str | None = None,
    ) -> SalidaProceso:
        """Reserva atomicamente un trabajo nuevo; nunca busca una continuacion."""
        archivo = Path(nombre_archivo)
        if archivo.name != nombre_archivo or not archivo.suffix:
            raise ValueError("La salida requiere un nombre de archivo simple con extension")
        nombre = sanitizar_nombre_subcarpeta(archivo.stem)
        trabajo = sanitizar_nombre_subcarpeta(nombre_trabajo or nombre)
        rama = self.rama(modulo)
        reservas = rama / self.configuracion["carpeta_reservas"]
        reservas.mkdir(parents=True, exist_ok=True)
        numero = 0
        while True:
            sufijo = self.configuracion["sufijo_copia"].format(numero=numero) if numero else ""
            nombre_carpeta = trabajo + sufijo
            nombre_final = nombre + sufijo + archivo.suffix
            ocupada = any(
                (rama / estado / nombre_carpeta).exists()
                or (rama / estado / nombre_final).exists()
                for estado in self.configuracion["estados"].values()
            )
            if ocupada:
                numero += 1
                continue
            try:
                # La reserva persiste al mover el trabajo entre estados.
                (reservas / nombre_carpeta).mkdir()
            except FileExistsError:
                numero += 1
                continue
            directorio = rama / self.configuracion["estados"]["en_proceso"] / nombre_carpeta
            directorio.mkdir(parents=True, exist_ok=False)
            return SalidaProceso(rama, directorio, nombre_final, self.configuracion)
