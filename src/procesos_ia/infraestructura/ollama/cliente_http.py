"""Cliente HTTP nativo y ligero para el servicio local de Ollama."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any

from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.infraestructura.ollama.modelos import (
    DiagnosticoOllama,
    EstadoServicioOllama,
    InformacionModelo,
    OpcionesInferencia,
)


class ClienteHttpOllama:
    """Cliente HTTP desacoplado y sin dependencias externas para Ollama."""

    def __init__(
        self,
        url_base: str = "http://127.0.0.1:11434",
        tiempo_limite_defecto: float = 30.0,
        reintentos_maximos: int = 2,
    ) -> None:
        self._url_base = url_base.rstrip("/")
        self._tiempo_limite = tiempo_limite_defecto
        self._reintentos = reintentos_maximos

    @property
    def url_base(self) -> str:
        return self._url_base

    def verificar_estado(self) -> DiagnosticoOllama:
        """Determina con precision si Ollama esta disponible, detenido o no instalado."""
        ruta_ejecutable = self._localizar_ejecutable()
        version_cliente = self._obtener_version_cliente(ruta_ejecutable)

        url_version = f"{self._url_base}/api/version"
        try:
            solicitud = urllib.request.Request(url_version, method="GET")
            with urllib.request.urlopen(solicitud, timeout=3.0) as respuesta:
                if respuesta.status == 200:
                    datos = json.loads(respuesta.read().decode("utf-8"))
                    version_servidor = str(datos.get("version", "desconocida"))
                    return DiagnosticoOllama(
                        estado=EstadoServicioOllama.DISPONIBLE,
                        version_cliente=version_cliente,
                        version_servidor=version_servidor,
                        ruta_ejecutable=ruta_ejecutable,
                        url_base=self._url_base,
                        mensaje="Servicio Ollama activo y listo para recibir peticiones",
                    )
        except urllib.error.HTTPError as error_http:
            return DiagnosticoOllama(
                estado=EstadoServicioOllama.ERROR_CONEXION,
                version_cliente=version_cliente,
                version_servidor=None,
                ruta_ejecutable=ruta_ejecutable,
                url_base=self._url_base,
                mensaje=f"Servicio Ollama respondio con error HTTP {error_http.code}: {error_http.reason}",
            )
        except (urllib.error.URLError, TimeoutError, OSError):
            pass

        if ruta_ejecutable is not None:
            return DiagnosticoOllama(
                estado=EstadoServicioOllama.DETENIDO,
                version_cliente=version_cliente,
                version_servidor=None,
                ruta_ejecutable=ruta_ejecutable,
                url_base=self._url_base,
                mensaje="Ollama esta instalado localmente pero el servicio esta detenido",
            )

        return DiagnosticoOllama(
            estado=EstadoServicioOllama.NO_INSTALADO,
            version_cliente=None,
            version_servidor=None,
            ruta_ejecutable=None,
            url_base=self._url_base,
            mensaje="No se encontro el ejecutable de Ollama en el sistema",
        )

    def listar_modelos(self) -> list[InformacionModelo]:
        """Consulta los modelos instalados localmente y sus metadatos tecnicos."""
        url = f"{self._url_base}/api/tags"
        datos = self._ejecutar_solicitud_json(url, metodo="GET", cuerpo=None)

        modelos: list[InformacionModelo] = []
        for item in datos.get("models", []):
            detalles = item.get("details", {})
            modelos.append(
                InformacionModelo(
                    nombre=item.get("name", ""),
                    tamano_bytes=int(item.get("size", 0)),
                    familia=str(detalles.get("family", "")),
                    formato=str(detalles.get("format", "")),
                    parametros=str(detalles.get("parameter_size", "")),
                    cuantizacion=str(detalles.get("quantization_level", "")),
                    modificado_utc=str(item.get("modified_at", "")),
                )
            )
        return modelos

    def generar_estructurado(
        self,
        modelo: str,
        prompt: str,
        esquema_salida: dict[str, Any] | None = None,
        opciones: OpcionesInferencia | None = None,
    ) -> dict[str, Any]:
        """Solicita inferencia a Ollama con salida garantizada en formato JSON."""
        opcs = opciones or OpcionesInferencia()
        cuerpo: dict[str, Any] = {
            "model": modelo,
            "prompt": prompt,
            "stream": False,
            "format": esquema_salida or "json",
            "keep_alive": opcs.keep_alive,
            "options": {
                "temperature": opcs.temperatura,
                "num_ctx": opcs.num_ctx,
                "top_p": opcs.top_p,
            },
        }
        if opcs.seed is not None:
            cuerpo["options"]["seed"] = opcs.seed

        url = f"{self._url_base}/api/generate"
        respuesta = self._ejecutar_solicitud_json(
            url,
            metodo="POST",
            cuerpo=cuerpo,
            tiempo_limite=opcs.tiempo_limite_segundos,
        )

        texto_crudo = respuesta.get("response", "{}")
        try:
            return json.loads(texto_crudo)
        except json.JSONDecodeError:
            return {"error_sintaxis": "Respuesta no es JSON valido", "texto": texto_crudo}

    def liberar_memoria_modelo(self, modelo: str) -> bool:
        """Descarga inmediatamente el modelo de la VRAM/RAM (keep_alive: 0)."""
        url = f"{self._url_base}/api/generate"
        cuerpo = {"model": modelo, "keep_alive": 0}
        try:
            self._ejecutar_solicitud_json(url, metodo="POST", cuerpo=cuerpo, tiempo_limite=10.0)
            return True
        except ErrorProcesamiento:
            return False

    def _ejecutar_solicitud_json(
        self,
        url: str,
        metodo: str,
        cuerpo: dict[str, Any] | None,
        tiempo_limite: float | None = None,
    ) -> dict[str, Any]:
        limite = tiempo_limite or self._tiempo_limite
        datos_bytes = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
        cabeceras = {"Content-Type": "application/json"} if cuerpo is not None else {}

        ultimo_error: Exception | None = None
        for intento in range(self._reintentos + 1):
            try:
                solicitud = urllib.request.Request(
                    url, data=datos_bytes, headers=cabeceras, method=metodo
                )
                with urllib.request.urlopen(solicitud, timeout=limite) as resp:
                    contenido = resp.read().decode("utf-8")
                    try:
                        return json.loads(contenido)
                    except json.JSONDecodeError as err_json:
                        raise ErrorProcesamiento(
                            f"Respuesta de Ollama ({url}) no es un JSON valido: {err_json}"
                        ) from err_json
            except urllib.error.HTTPError as error_http:
                if 400 <= error_http.code < 500:
                    try:
                        cuerpo_error = error_http.read().decode("utf-8")
                        detalle = json.loads(cuerpo_error).get("error", error_http.reason)
                    except Exception:
                        detalle = error_http.reason
                    raise ErrorProcesamiento(
                        f"Error HTTP {error_http.code} en Ollama ({url}): {detalle}"
                    ) from error_http
                ultimo_error = error_http
                if intento < self._reintentos:
                    time.sleep(0.5 * (2**intento))
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                ultimo_error = error
                if intento < self._reintentos:
                    time.sleep(0.5 * (2**intento))

        raise ErrorProcesamiento(
            f"Fallo en peticion HTTP a Ollama ({url}): {ultimo_error}"
        )

    def _localizar_ejecutable(self) -> Path | None:
        hallado = shutil.which("ollama")
        if hallado:
            return Path(hallado)

        # Rutas comunes en Windows
        ruta_usuario = Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe"
        if ruta_usuario.is_file():
            return ruta_usuario

        ruta_sistema = Path("C:/Program Files/Ollama/ollama.exe")
        if ruta_sistema.is_file():
            return ruta_sistema

        return None

    def _obtener_version_cliente(self, ruta_ejecutable: Path | None) -> str | None:
        if ruta_ejecutable is None:
            return None
        try:
            proceso = subprocess.run(
                [str(ruta_ejecutable), "--version"],
                capture_output=True,
                text=True,
                timeout=3.0,
                check=False,
            )
            salida = (proceso.stdout + " " + proceso.stderr).strip()
            coincidencia = re.search(
                r"version\s+(?:is\s+)?([0-9]+\.[0-9]+(?:\.[0-9]+)?)", salida, re.I
            )
            if coincidencia:
                return coincidencia.group(1)
        except (OSError, subprocess.SubprocessError):
            pass
        return None
