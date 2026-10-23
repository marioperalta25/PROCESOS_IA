"""Transporte JSON común, con exclusión de inferencias y lectura acotada."""

import errno
import json
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from procesos_ia.dominio.excepciones import ErrorConexionRechazada, ErrorProcesamiento, OperacionCancelada


@contextmanager
def controlar_inferencia(bloqueo, aplica: bool, mensaje: str):
    if not aplica:
        yield
        return
    if not bloqueo.acquire(blocking=False):
        raise ErrorProcesamiento(mensaje)
    try:
        yield
    finally:
        bloqueo.release()


def ejecutar_solicitud_json(url, metodo, cuerpo, tiempo_limite, reintentos,
                            tiempo_defecto, reintentos_defecto,
                            limite_respuesta_bytes, mensaje_limite, *, al_evento=None,
                            cancelacion=None, limite_linea_bytes=None, mensaje_invalido=""):
    limite = tiempo_limite or tiempo_defecto
    num_reintentos = reintentos_defecto if reintentos is None else reintentos
    if al_evento is not None:
        num_reintentos = 0
    datos_bytes = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    cabeceras = {"Content-Type": "application/json"} if cuerpo is not None else {}

    ultimo_error: Exception | None = None
    for intento in range(num_reintentos + 1):
        try:
            _comprobar_cancelacion(cancelacion)
            solicitud = urllib.request.Request(
                url, data=datos_bytes, headers=cabeceras, method=metodo
            )
            vencimiento = time.monotonic() + limite
            with urllib.request.urlopen(solicitud, timeout=limite) as resp:
                if al_evento is not None:
                    return _leer_flujo(resp, al_evento, cancelacion, limite_respuesta_bytes,
                                       limite_linea_bytes, mensaje_limite, mensaje_invalido,
                                       vencimiento)
                crudo = resp.read() if limite_respuesta_bytes is None else resp.read(limite_respuesta_bytes + 1)
                if limite_respuesta_bytes is not None and len(crudo) > limite_respuesta_bytes:
                    raise ErrorProcesamiento(mensaje_limite)
                contenido = crudo.decode("utf-8")
                try:
                    return json.loads(contenido)
                except json.JSONDecodeError as err_json:
                    raise ErrorProcesamiento(
                        f"Respuesta de Ollama ({url}) no es un JSON valido: {err_json}"
                    ) from err_json
        except urllib.error.HTTPError as error_http:
            if 400 <= error_http.code < 500:
                try:
                    crudo_error = (error_http.read() if limite_respuesta_bytes is None
                                   else error_http.read(limite_respuesta_bytes + 1))
                    cuerpo_error = crudo_error.decode("utf-8")
                    detalle = json.loads(cuerpo_error).get("error", error_http.reason)
                except Exception:
                    detalle = error_http.reason
                raise ErrorProcesamiento(
                    f"Error HTTP {error_http.code} en Ollama ({url}): {detalle}"
                ) from error_http
            ultimo_error = error_http
            if intento < num_reintentos:
                time.sleep(0.5 * (2**intento))
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            _comprobar_cancelacion(cancelacion)
            ultimo_error = error
            if intento < num_reintentos:
                time.sleep(0.5 * (2**intento))

    causa = getattr(ultimo_error, "reason", ultimo_error)
    if (isinstance(causa, ConnectionRefusedError)
            or getattr(causa, "errno", None) == errno.ECONNREFUSED
            or getattr(causa, "winerror", None) == 10061):
        raise ErrorConexionRechazada("El destino rechazo la conexion con Ollama") from ultimo_error
    raise ErrorProcesamiento(
        f"Fallo en peticion HTTP a Ollama ({url}): {ultimo_error}"
    ) from ultimo_error


def _comprobar_cancelacion(cancelacion) -> None:
    if cancelacion is not None and cancelacion.is_set():
        raise OperacionCancelada()


def _leer_flujo(respuesta, al_evento, cancelacion, maximo, maximo_linea,
                mensaje_limite, mensaje_invalido, vencimiento) -> dict:
    """Lee NDJSON por líneas acotadas; nunca reintenta una generación parcial."""
    leidos = 0
    while True:
        _comprobar_cancelacion(cancelacion)
        if time.monotonic() >= vencimiento:
            raise TimeoutError()
        linea = respuesta.readline(min(maximo_linea, maximo - leidos) + 1)
        _comprobar_cancelacion(cancelacion)
        if time.monotonic() >= vencimiento:
            raise TimeoutError()
        if not linea:
            raise ErrorProcesamiento(mensaje_invalido)
        leidos += len(linea)
        if leidos > maximo or len(linea) > maximo_linea:
            raise ErrorProcesamiento(mensaje_limite)
        if not linea.strip():
            continue
        try:
            evento = json.loads(linea)
        except (UnicodeDecodeError, ValueError) as error:
            raise ErrorProcesamiento(mensaje_invalido) from error
        if not isinstance(evento, dict) or evento.get("error"):
            raise ErrorProcesamiento(mensaje_invalido)
        al_evento(evento)
        if evento.get("done") is True:
            return evento

