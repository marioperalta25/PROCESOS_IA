"""Estimación acotada por modelo y contexto, aprendida de contadores reales."""

from collections import OrderedDict, deque
from math import ceil, isfinite
from threading import Lock


class EstimadorContexto:
    def __init__(self, limites: dict) -> None:
        self.limites = limites
        self._perfiles = OrderedDict()
        self._bloqueo = Lock()
        self._version = 0

    def factor(self, modelo: str, contexto: int) -> float:
        return self.perfil(modelo, contexto)[0]

    def perfil(self, modelo: str, contexto: int) -> tuple[float, int]:
        with self._bloqueo:
            perfil = self._perfiles.get((modelo, contexto))
            factor = perfil["factor"] if perfil else self.limites["bytes_por_token_estimados"]
            return factor, self._version

    def coste(self, mensajes: list[dict], modelo: str = "", contexto: int = 0, *,
              factor: float | None = None) -> int:
        factor = self.factor(modelo, contexto) if factor is None else factor
        return sum(ceil(len(m["content"].encode("utf-8")) / factor)
                   + self.limites["separacion_contexto_tokens"] for m in mensajes)

    def registrar(self, modelo: str, contexto: int, mensajes: list[dict], metricas: dict,
                  presupuesto: int, version: int | None = None) -> None:
        tokens = metricas.get("prompt_eval_count")
        tamano = sum(len(m["content"].encode("utf-8")) for m in mensajes)
        if (type(tokens) is not int or not 0 < tokens < presupuesto
                or tamano < self.limites["calibracion_bytes_minimos"]):
            return
        muestra = tamano / tokens
        if not isfinite(muestra):
            return
        with self._bloqueo:
            if version is not None and version != self._version:
                return
            clave = modelo, contexto
            perfil = self._perfiles.pop(clave, None)
            if perfil is None:
                perfil = {"factor": self.limites["bytes_por_token_estimados"],
                          "muestras": deque(maxlen=self.limites["calibracion_muestras"])}
            perfil["muestras"].append(muestra)
            if len(perfil["muestras"]) >= self.limites["calibracion_minimo_muestras"]:
                objetivo = min(perfil["muestras"]) / self.limites["calibracion_margen"]
                objetivo = max(self.limites["calibracion_factor_minimo"],
                               min(self.limites["calibracion_factor_maximo"], objetivo))
                # Relajar gradualmente; aumentar la prudencia sin demora.
                perfil["factor"] = min(objetivo, perfil["factor"]
                                       * (1 + self.limites["calibracion_paso_maximo"]))
            self._perfiles[clave] = perfil
            while len(self._perfiles) > self.limites["modelos_cache"]:
                self._perfiles.popitem(last=False)

    def limpiar(self) -> None:
        with self._bloqueo:
            self._perfiles.clear()
            self._version += 1
