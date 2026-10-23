"""Historial JSON acotado, reemplazo atómico y exclusión entre instancias."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from threading import Lock
from uuid import UUID, uuid4

from procesos_ia.dominio.excepciones import ErrorProcesamiento


class RepositorioChat:
    def __init__(self, directorio: Path, parametros: dict) -> None:
        self.directorio = directorio
        self.parametros = parametros
        self._bloqueo = Lock()

    def nuevo(self) -> dict:
        return {"id": uuid4().hex, "titulo": self.parametros["textos"]["nuevo"],
                "resumen": "", "resumidos": 0, "mensajes": [], "actualizado": "", "modelo": ""}

    def _ruta(self, identificador: str) -> Path:
        try:
            valido = UUID(identificador).hex == identificador
        except (ValueError, TypeError, AttributeError):
            valido = False
        if not valido:
            raise ErrorProcesamiento(self.parametros["textos"]["historial_invalido"])
        return self.directorio / f"{identificador}.json"

    def existe(self, identificador: str) -> bool:
        return self._ruta(identificador).is_file()

    @contextmanager
    def operacion(self):
        if not self._bloqueo.acquire(blocking=False):
            raise ErrorProcesamiento(self.parametros["textos"]["bloqueado"])
        archivo = None
        adquirido = False
        try:
            self.directorio.mkdir(parents=True, exist_ok=True)
            archivo = (self.directorio / ".bloqueo").open("a+b")
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
                    fcntl.flock(archivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
                adquirido = True
            except OSError as error:
                raise ErrorProcesamiento(self.parametros["textos"]["bloqueado"]) from error
            # Solo temporales de transacciones no confirmadas; nunca historiales.
            for temporal in self.directorio.glob("*.tmp"):
                temporal.unlink()
            yield
        finally:
            if archivo is not None:
                if adquirido:
                    archivo.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(archivo.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(archivo, fcntl.LOCK_UN)
                archivo.close()
            self._bloqueo.release()

    def uso(self) -> int:
        return sum(p.stat().st_size for p in self.directorio.iterdir() if p.is_file()) if self.directorio.exists() else 0

    def leer(self, identificador: str) -> dict:
        ruta = self._ruta(identificador)
        try:
            with ruta.open("rb") as archivo:
                crudo = archivo.read(self.parametros["limites"]["conversacion_bytes"] + 1)
            datos = json.loads(crudo)
            datos.setdefault("modelo", "")
            if not (len(crudo) <= self.parametros["limites"]["conversacion_bytes"]
                    and datos["id"] == identificador and isinstance(datos["titulo"], str)
                    and isinstance(datos["resumen"], str) and isinstance(datos["actualizado"], str)
                    and isinstance(datos["modelo"], str)
                    and isinstance(datos["mensajes"], list) and isinstance(datos["resumidos"], int)
                    and 0 <= datos["resumidos"] <= len(datos["mensajes"])):
                raise ValueError()
            for mensaje in datos["mensajes"]:
                if not (mensaje["rol"] in ("user", "assistant")
                        and isinstance(mensaje["texto"], str) and isinstance(mensaje["id"], str)
                        and mensaje["estado"] in ("completo", "pendiente", "fallido", "cancelado")):
                    raise ValueError()
            if "contexto" in datos and (type(datos["contexto"]) is not int or datos["contexto"] <= 0):
                raise ValueError()
            if "temperatura" in datos and (type(datos["temperatura"]) not in (int, float)
                                            or not math.isfinite(datos["temperatura"])):
                raise ValueError()
            return datos
        except (OSError, ValueError, KeyError, TypeError, AssertionError) as error:
            raise ErrorProcesamiento(self.parametros["textos"]["historial_invalido"]) from error

    def listar(self) -> list[dict]:
        # Una conversación acotada a la vez; la lista conserva solo metadatos.
        salida = []
        for ruta in self.directorio.glob("*.json"):
            datos = self.leer(ruta.stem)
            salida.append({k: datos[k] for k in ("id", "titulo", "actualizado")})
        return sorted(salida, key=lambda d: d["actualizado"], reverse=True)

    def guardar_bajo_bloqueo(self, datos: dict) -> None:
        ruta = self._ruta(datos["id"])
        limites, textos = self.parametros["limites"], self.parametros["textos"]
        if ruta.exists():
            anterior = self.leer(datos["id"])
            if anterior["mensajes"] and anterior["modelo"] != datos.get("modelo", ""):
                raise ErrorProcesamiento(textos["modelo_fijo"])
        if not ruta.exists() and len(list(self.directorio.glob("*.json"))) >= limites["conversaciones"]:
            raise ErrorProcesamiento(textos["cuota"])
        datos["actualizado"] = datetime.now(timezone.utc).isoformat()
        crudo = json.dumps(datos, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(crudo) > limites["conversacion_bytes"]:
            raise ErrorProcesamiento(textos["lleno_chat"])
        if self.uso() + len(crudo) > limites["historial_bytes"]:
            raise ErrorProcesamiento(textos["cuota"])
        temporal = ruta.with_suffix(".tmp")
        try:
            with temporal.open("xb") as archivo:
                archivo.write(crudo)
                archivo.flush()
                os.fsync(archivo.fileno())
            os.replace(temporal, ruta)
        finally:
            temporal.unlink(missing_ok=True)

    def guardar(self, datos: dict, version_esperada: str | None = None) -> None:
        with self.operacion():
            existe = self.existe(datos["id"])
            if ((version_esperada and not existe) or (version_esperada is not None and existe
                    and self.leer(datos["id"])["actualizado"] != version_esperada)):
                raise ErrorProcesamiento(self.parametros["textos"]["bloqueado"])
            self.guardar_bajo_bloqueo(datos)

    def borrar(self, identificador: str) -> None:
        with self.operacion():
            self._ruta(identificador).unlink(missing_ok=True)

    def comprobar_respuesta(self, datos: dict) -> None:
        # El bloqueo se conserva durante la inferencia: nadie puede ocupar esta
        # reserva. Se contabilizan también los picos de reemplazo atómico.
        limites = self.parametros["limites"]
        ocupado = len(json.dumps(datos, ensure_ascii=False).encode("utf-8"))
        reserva = ((limites["respuesta_bytes"] + limites["resumen_bytes"])
                   * limites["factor_escape_json"] + limites["reserva_metadatos_bytes"])
        final_maximo = ocupado + reserva
        if final_maximo > limites["conversacion_bytes"]:
            raise ErrorProcesamiento(self.parametros["textos"]["lleno_chat"])
        ruta = self._ruta(datos["id"])
        original = ruta.stat().st_size if ruta.exists() else 0
        if self.uso() - original + ocupado + final_maximo > limites["historial_bytes"]:
            raise ErrorProcesamiento(self.parametros["textos"]["cuota"])
