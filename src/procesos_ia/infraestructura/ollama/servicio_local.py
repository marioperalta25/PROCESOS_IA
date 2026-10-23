"""Supervision de una instancia local de Ollama con diagnostico acotado."""

from __future__ import annotations

from collections import deque
import ipaddress
import os
from pathlib import Path
import subprocess
import sys
from threading import Event, Lock, Thread
import time
import tomllib
from typing import Callable
from urllib.parse import urlsplit

from procesos_ia.dominio.excepciones import ErrorConexionRechazada, ErrorProcesamiento


class ServicioLocalOllama:
    """Serializa arranques y conserva el proceso propio sin detener servicios ajenos."""

    def __init__(self, url_base: str, ruta_parametros: Path | None = None) -> None:
        self._url_base = url_base
        ruta = ruta_parametros or (
            Path(__file__).resolve().parents[4]
            / "recursos" / "configuracion" / "arranque_ollama.toml"
        )
        self._parametros = tomllib.loads(ruta.read_text(encoding="utf-8"))
        self._bloqueo = Lock()
        self._proceso: subprocess.Popen | None = None
        self._lectura: Thread | None = None
        self._errores = deque(maxlen=self._parametros["limite_diagnostico_bytes"])

    def _destino_local(self) -> str:
        destino = urlsplit(self._url_base)
        host = destino.hostname
        if host == "localhost":
            host = "127.0.0.1"
        try:
            local = ipaddress.ip_address(host or "").is_loopback
            puerto = destino.port
        except ValueError as error:
            raise ErrorProcesamiento("Destino de Ollama invalido") from error
        if (not local or destino.scheme != "http" or puerto is None
                or destino.username or destino.password or destino.path not in ("", "/")
                or destino.query or destino.fragment):
            raise ErrorProcesamiento("Solo se puede iniciar Ollama en una URL HTTP local con puerto explicito")
        direccion = f"[{host}]" if ":" in host else host
        return f"{direccion}:{puerto}"

    def _recoger_errores(self, proceso: subprocess.Popen) -> None:
        assert proceso.stderr is not None
        try:
            while bloque := proceso.stderr.read(self._parametros["tamano_lectura_bytes"]):
                self._errores.extend(bloque)
        finally:
            proceso.stderr.close()

    def iniciar(
        self, ruta: Path, consultar: Callable[..., list], tiempo_espera: float,
        cancelacion: Event | None = None,
    ) -> bool:
        """Verifica destino y disponibilidad; un timeout no mata el servidor creado."""
        destino = self._destino_local()
        if tiempo_espera <= 0:
            raise ErrorProcesamiento("El tiempo de arranque debe ser positivo")
        if not self._bloqueo.acquire(blocking=False):
            raise ErrorProcesamiento("Ya hay un arranque de Ollama en curso")
        try:
            if cancelacion is not None and cancelacion.is_set():
                return False
            fin = time.monotonic() + tiempo_espera
            limite = self._parametros["limite_consulta_segundos"]
            try:
                consultar(tiempo_limite=min(limite, tiempo_espera), reintentos=0)
                return True
            except ErrorConexionRechazada:
                pass
            if cancelacion is not None and cancelacion.is_set():
                return False
            if time.monotonic() >= fin:
                raise ErrorProcesamiento("Ollama aun no responde; no se confirma el arranque")
            if self._proceso is None or self._proceso.poll() is not None:
                if self._lectura is not None and self._lectura.is_alive():
                    raise ErrorProcesamiento("El proceso anterior aun esta cerrando su diagnostico")
                self._errores.clear()
                entorno = dict(os.environ, OLLAMA_HOST=destino)
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                try:
                    self._proceso = subprocess.Popen(
                        [str(ruta), "serve"], stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                        env=entorno, creationflags=flags, shell=False,
                    )
                except OSError as error:
                    raise ErrorProcesamiento("No se pudo ejecutar Ollama") from error
                self._lectura = Thread(
                    target=self._recoger_errores, args=(self._proceso,), daemon=True,
                )
                self._lectura.start()
            while (restante := fin - time.monotonic()) > 0:
                if cancelacion is not None and cancelacion.is_set():
                    return False
                codigo = self._proceso.poll()
                if codigo is not None:
                    self._lectura.join(timeout=self._parametros["intervalo_sondeo_segundos"])
                    detalle = bytes(self._errores).decode("utf-8", errors="replace").strip()
                    raise ErrorProcesamiento(f"Ollama termino con codigo {codigo}: {detalle}")
                try:
                    consultar(tiempo_limite=min(limite, restante), reintentos=0)
                    return True
                except ErrorConexionRechazada:
                    espera = min(self._parametros["intervalo_sondeo_segundos"], restante)
                    if cancelacion is not None:
                        cancelacion.wait(espera)
                    else:
                        time.sleep(espera)
            raise ErrorProcesamiento("Ollama aun no responde; no se confirma el arranque")
        finally:
            self._bloqueo.release()
