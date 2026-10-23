"""Texto completo o progresivo mediante el transporte del cliente compartido."""

from threading import Event
from typing import Callable
from procesos_ia.dominio.excepciones import ErrorProcesamiento


def solicitar_chat(cliente, mensajes: list[dict], modelo: str, contexto: int,
                   temperatura: float, parametros: dict, resumir: bool = False, *,
                   al_fragmento: Callable[[str], None] | None = None,
                   cancelacion: Event | None = None,
                   al_metricas: Callable[[dict], None] | None = None) -> str:
    limites, textos = parametros["limites"], parametros["textos"]
    cuerpo = {
        "model": modelo, "messages": mensajes, "stream": al_fragmento is not None,
        "keep_alive": limites["keep_alive"],
        "options": {"num_ctx": contexto, "temperature": temperatura,
                    "num_predict": limites["respuesta_tokens"]},
    }
    partes, bytes_texto = [], 0
    maximo = limites["resumen_bytes"] if resumir else limites["respuesta_bytes"]

    def recibir(evento: dict) -> None:
        nonlocal bytes_texto
        mensaje = evento.get("message")
        fragmento = mensaje.get("content") if isinstance(mensaje, dict) else None
        if not isinstance(fragmento, str):
            raise ErrorProcesamiento(textos["respuesta_invalida"])
        bytes_texto += len(fragmento.encode("utf-8"))
        if bytes_texto > maximo:
            raise ErrorProcesamiento(textos["respuesta_grande"])
        if fragmento:
            partes.append(fragmento)
            al_fragmento(fragmento)

    opciones = {"cancelacion": cancelacion}
    if al_fragmento is not None:
        opciones.update(al_evento=recibir, limite_linea_bytes=limites["http_linea_bytes"])
    datos = cliente._ejecutar_solicitud_json(
        cliente.url_base + parametros["rutas"]["endpoint"], "POST", cuerpo,
        tiempo_limite=limites["tiempo_segundos"], reintentos=0,
        limite_respuesta_bytes=limites["http_bytes"],
        **opciones,
    )
    mensaje = datos.get("message") if isinstance(datos, dict) else None
    texto = "".join(partes) if al_fragmento is not None else (
        mensaje.get("content") if isinstance(mensaje, dict) else None)
    if not isinstance(texto, str) or not texto.strip() or datos.get("done") is not True:
        raise ErrorProcesamiento(textos["respuesta_invalida"])
    if len(texto.encode("utf-8")) > maximo:
        raise ErrorProcesamiento(textos["respuesta_grande"])
    if al_metricas is not None:
        al_metricas({clave: datos[clave] for clave in (
            "prompt_eval_count", "prompt_eval_cached_count", "prompt_eval_duration",
            "eval_count", "eval_duration", "load_duration", "total_duration",
        ) if type(datos.get(clave)) is int and datos[clave] >= 0})
    return texto.strip()
