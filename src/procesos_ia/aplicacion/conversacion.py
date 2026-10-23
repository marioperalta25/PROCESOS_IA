"""Contexto aislado y generación de una respuesta con memoria acotada."""

from copy import deepcopy
from functools import partial
from threading import Event
from typing import Callable
from uuid import uuid4

from procesos_ia.dominio.excepciones import ErrorProcesamiento, OperacionCancelada
from procesos_ia.aplicacion.contratos_chat import GeneradorConversacion, RepositorioConversaciones
from procesos_ia.aplicacion.estimador_contexto import EstimadorContexto


class ServicioConversacion:
    def __init__(self, repositorio: RepositorioConversaciones,
                 generar: GeneradorConversacion, parametros: dict, preparar_modelo=None) -> None:
        self.repositorio, self._generar, self.parametros = repositorio, generar, parametros
        self._preparar_modelo = preparar_modelo
        self.estimador = EstimadorContexto(parametros["limites"])

    def _presupuesto(self, contexto: int) -> int:
        limites = self.parametros["limites"]
        return contexto - limites["respuesta_tokens"] - limites["margen_tokens"]

    def _coste(self, mensajes: list[dict], modelo: str = "", contexto: int = 0) -> int:
        return self.estimador.coste(mensajes, modelo, contexto)

    def validar_memoria(self, texto: str) -> None:
        limites = self.parametros["limites"]
        if (len(texto.encode("utf-8")) > limites["resumen_bytes"]
                or self._coste([{"content": self.parametros["textos"]["prefijo_resumen"] + texto}])
                > limites["memoria_tokens"]):
            raise ErrorProcesamiento(self.parametros["textos"]["memoria_extensa"])

    def guardar_memoria(self, datos: dict, texto: str) -> dict:
        self.validar_memoria(texto)
        actualizado = deepcopy(datos)
        actualizado["resumen"] = texto
        self.repositorio.guardar(actualizado, version_esperada=datos["actualizado"])
        return actualizado

    def preparar_contexto(self, datos: dict, entrada: str, contexto: int, *,
                         factor: float | None = None) -> tuple[list[dict], bool]:
        textos = self.parametros["textos"]
        base = [{"role": "system", "content": textos["sistema"]}]
        actual = {"role": "user", "content": entrada}
        presupuesto = self._presupuesto(contexto)
        factor = self.estimador.factor(datos.get("modelo", ""), contexto) if factor is None else factor
        calcular = partial(self.estimador.coste, factor=factor)
        if calcular(base + [actual]) > presupuesto:
            raise ErrorProcesamiento(textos["entrada_grande"])
        memoria = {"role": "user", "content": textos["prefijo_resumen"] + datos["resumen"]}
        if (datos["resumen"] and calcular([memoria]) <= self.parametros["limites"]["memoria_tokens"]
                and calcular(base + [memoria, actual]) <= presupuesto):
            base.append(memoria)
        completos = datos["mensajes"]
        turnos = []
        for i in range(len(completos) - 1):
            usuario, respuesta = completos[i:i + 2]
            if (usuario["rol"] == "user" and respuesta["rol"] == "assistant"
                    and usuario["estado"] == respuesta["estado"] == "completo"):
                turnos.append([{"role": m["rol"], "content": m["texto"]} for m in (usuario, respuesta)])
        recientes = []
        coste = calcular(base + [actual])
        for turno in reversed(turnos):
            coste_turno = calcular(turno)
            if coste + coste_turno > presupuesto:
                break
            recientes = turno + recientes
            coste += coste_turno
        return base + recientes + [actual], len(recientes) < 2 * len(turnos)

    def responder(self, datos: dict, entrada: str, modelo: str, contexto: int,
                  temperatura: float, cancelacion: Event, reintentar: bool = False, *,
                  al_fragmento: Callable[[str], None] | None = None) -> tuple[dict, str]:
        datos = deepcopy(datos)
        limites, textos = self.parametros["limites"], self.parametros["textos"]
        if not modelo:
            raise ErrorProcesamiento(textos["sin_modelo"])
        if datos["mensajes"] and not datos.get("modelo"):
            raise ErrorProcesamiento(textos["modelo_antiguo"])
        if datos["mensajes"] and datos["modelo"] != modelo:
            raise ErrorProcesamiento(textos["modelo_fijo"])
        if not entrada.strip() or len(entrada.encode("utf-8")) > limites["entrada_bytes"]:
            raise ErrorProcesamiento(textos["entrada_grande"])
        with self.repositorio.operacion():
            if self.repositorio.existe(datos["id"]):
                vigente = self.repositorio.leer(datos["id"])
                if not vigente["mensajes"]:
                    vigente["modelo"] = datos.get("modelo", "")
                if vigente != datos:
                    raise ErrorProcesamiento(textos["bloqueado"])
            elif datos["actualizado"]:
                raise ErrorProcesamiento(textos["historial_invalido"])
            datos["modelo"] = modelo
            solicitado = datos.get("contexto", contexto)
            contexto = self._preparar_modelo(modelo, solicitado) if self._preparar_modelo else solicitado
            datos["contexto"] = contexto
            temperatura = datos.setdefault("temperatura", temperatura)
            factor, version_estimacion = self.estimador.perfil(modelo, contexto)
            mensajes, reducido = self.preparar_contexto(datos, entrada, contexto, factor=factor)
            if reintentar:
                pendiente = datos["mensajes"][-1]
                if (pendiente["rol"] != "user" or pendiente["estado"] == "completo"
                        or pendiente["texto"] != entrada):
                    raise ErrorProcesamiento(textos["pendiente"])
                pendiente["estado"] = "pendiente"
            else:
                if not datos["mensajes"] and not datos["actualizado"]:
                    datos["titulo"] = entrada.splitlines()[0][:limites["titulo_caracteres"]]
                datos["mensajes"].append({"id": uuid4().hex, "rol": "user",
                                           "texto": entrada, "estado": "pendiente"})
            self.repositorio.comprobar_respuesta(datos)
            self.repositorio.guardar_bajo_bloqueo(datos)
            aviso = textos["exito"]
            try:
                if reducido:
                    aviso = textos["contexto_reducido"]
                memoria_incluida = bool(datos["resumen"] and len(mensajes) > 2
                                       and mensajes[1]["content"] == textos["prefijo_resumen"] + datos["resumen"])
                if datos["resumen"] and not memoria_incluida:
                    aviso += " " + textos["memoria_omitida"]
                metricas = {"contexto_tokens_estimados": self.estimador.coste(mensajes, factor=factor),
                            "bytes_por_token_estimados": factor,
                            "mensajes_contexto": len(mensajes), "memoria_incluida": memoria_incluida,
                            "historial_recortado": reducido}
                if cancelacion.is_set():
                    datos["mensajes"][-1]["estado"] = "cancelado"
                    aviso = textos["cancelado"]
                else:
                    try:
                        respuesta = self._generar(mensajes, modelo, contexto, temperatura,
                                                  al_fragmento=al_fragmento, cancelacion=cancelacion,
                                                  al_metricas=metricas.update)
                    except OperacionCancelada:
                        cancelacion.set()
                        respuesta = ""
                    datos["mensajes"][-1]["estado"] = "cancelado" if cancelacion.is_set() else "completo"
                    if not cancelacion.is_set():
                        datos["ultima_inferencia"] = metricas
                        datos["mensajes"].append({"id": uuid4().hex, "rol": "assistant",
                                                   "texto": respuesta, "estado": "completo", "modelo": modelo})
                    else:
                        aviso = textos["cancelado"]
                self.repositorio.guardar_bajo_bloqueo(datos)
                if not cancelacion.is_set():
                    self.estimador.registrar(modelo, contexto, mensajes, metricas,
                                             self._presupuesto(contexto), version_estimacion)
                if contexto != solicitado:
                    aviso += " " + textos["contexto_ajustado"].format(contexto=contexto)
                return datos, aviso
            except Exception:
                # La copia pendiente durable permite reintentar sin duplicar la entrada.
                raise
