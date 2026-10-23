"""Consulta acotada y cacheada de capacidades, sin cargar el modelo."""

from threading import Lock
from procesos_ia.dominio.excepciones import ErrorProcesamiento


class PreparadorChatOllama:
    def __init__(self, cliente, parametros: dict) -> None:
        self._cliente, self._parametros = cliente, parametros
        self._cache = {}
        self._version = 0
        self._bloqueo = Lock()

    def invalidar(self) -> None:
        with self._bloqueo:
            self._cache.clear()
            self._version += 1

    def preparar(self, modelo: str, contexto: int) -> int:
        with self._bloqueo:
            datos = self._cache.get(modelo)
            version = self._version
        if datos is None:
            limites = self._parametros["limites"]
            datos = self._cliente._ejecutar_solicitud_json(
                self._cliente.url_base + self._parametros["rutas"]["detalles_modelo"],
                "POST", {"model": modelo, "verbose": False},
                tiempo_limite=limites["consulta_modelo_segundos"], reintentos=0,
                limite_respuesta_bytes=limites["http_bytes"],
            )
            if not isinstance(datos, dict) or not datos:
                raise ErrorProcesamiento(self._parametros["textos"]["detalles_invalidos"])
            capacidades = datos.get("capabilities")
            informacion = datos.get("model_info", {})
            if ((capacidades is not None and not isinstance(capacidades, list))
                    or not isinstance(informacion, dict)):
                raise ErrorProcesamiento(self._parametros["textos"]["detalles_invalidos"])
            arquitectura = informacion.get("general.architecture")
            maximo = informacion.get(f"{arquitectura}.context_length") if arquitectura else None
            # No retener licencias, plantillas ni vocabularios en la caché.
            datos = {"compatible": capacidades is None or "completion" in capacidades,
                     "contexto": maximo if type(maximo) is int and maximo > 0 else None}
            with self._bloqueo:
                if self._version == version:
                    if len(self._cache) >= limites["modelos_cache"]:
                        self._cache.pop(next(iter(self._cache)))
                    self._cache[modelo] = datos
        if not datos["compatible"]:
            raise ErrorProcesamiento(self._parametros["textos"]["modelo_incompatible"])
        maximo = datos["contexto"]
        # Datos ausentes en versiones antiguas no prueban una capacidad inexistente.
        return min(contexto, maximo) if type(maximo) is int and maximo > 0 else contexto
