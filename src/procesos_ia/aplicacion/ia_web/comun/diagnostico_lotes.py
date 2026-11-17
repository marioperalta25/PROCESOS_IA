"""Modulo centralizado de metricas, calculos de calidad y logs garantizados para IA Web."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import re
from typing import Any

PATRONES_LIMITE_CUOTA = (
    r"alcanzaste el l[ií]mite de solicitudes",
    r"l[ií]mite de respuestas de ia",
    r"vuelve a intentarlo m[aá]s tarde",
    r"reached the limit of ai",
    r"too many requests",
    r"alcanzaste el l[ií]mite",
    r"l[ií]mite de respuestas",
)


def detectar_limite_cuota(texto_resp: str) -> bool:
    """Verifica si el texto devuelto por el asistente indica saturacion o limite de cuota."""
    if not texto_resp:
        return False
    for patron in PATRONES_LIMITE_CUOTA:
        if re.search(patron, texto_resp, re.IGNORECASE):
            return True
    return False


def evaluar_calidad_lote(
    filas_lote: list[dict[str, Any]], tamano_esperado: int
) -> tuple[int, int]:
    """Calcula matematicamente filas evaluadas exitosamente vs omitidas por el LLM."""
    evaluadas = sum(
        1 for f in filas_lote
        if str(f.get("_estado_ia") or f.get("estado_ia") or "").upper() == "EXITOSO" or bool(f.get("evaluacion_ia"))
    )
    omitidas = max(0, tamano_esperado - evaluadas)
    return evaluadas, omitidas


def notificar_inicio_proceso(
    callback_log: Callable[[str], None] | None,
    motor: str,
    total_filas: int,
    total_lotes: int,
    tamano_lote: int,
    rotacion_chat: int,
) -> None:
    """Emite log inicial con resumen cuantitativo de la corrida."""
    if callback_log:
        callback_log(
            f"[INFO] {motor}: {total_filas} filas en {total_lotes} lotes "
            f"({tamano_lote} f/lote, rotación cada {rotacion_chat} chats)"
        )


def notificar_envio_prompt_sistema(
    callback_log: Callable[[str], None] | None,
    longitud_caracteres: int,
) -> None:
    """Informa el envio del prompt inicial de instrucciones al chat."""
    if callback_log:
        callback_log(
            f"[INFO] Enviando prompt inicial del sistema ({longitud_caracteres:,} caracteres)..."
        )


def notificar_fallo_prompt_sistema(callback_log: Callable[[str], None] | None) -> None:
    """Informa error de envio del prompt de calibracion."""
    if callback_log:
        callback_log("[ERROR] No se pudo enviar el prompt inicial a Modo IA. Reintentando...")


def notificar_alerta_confirmacion_inicio(
    callback_log: Callable[[str], None] | None,
) -> None:
    """Alerta si el asistente no devolvio confirmacion del prompt inicial."""
    if callback_log:
        callback_log("[ALERTA] Modo IA no confirmó el prompt del sistema. Reintentando inicio...")


def notificar_envio_lote(
    callback_log: Callable[[str], None] | None,
    n_lote: int,
    total_lotes: int,
    fila_desde: int,
    fila_hasta: int,
    total_filas: int,
    delimitador: str = "|",
) -> None:
    """Notifica con precision el rango de filas enviado en el lote actual."""
    if callback_log:
        callback_log(
            f"[INFO] Enviando Lote {n_lote}/{total_lotes} "
            f"(filas {fila_desde}-{fila_hasta} de {total_filas}) con '{delimitador}'..."
        )


def notificar_fallo_envio_lote(
    callback_log: Callable[[str], None] | None, n_lote: int
) -> None:
    """Notifica error de inyeccion DOM en un lote especifico."""
    if callback_log:
        callback_log(f"[ERROR] Falló envío en Lote {n_lote}")


def notificar_respuesta_lote(
    callback_log: Callable[[str], None] | None,
    n_lote: int,
    total_lotes: int,
    duracion_seg: float,
) -> None:
    """Registra tiempo real de inferencia para el lote respondido."""
    if callback_log:
        callback_log(f"[OK] Lote {n_lote}/{total_lotes} respondido en {duracion_seg:.1f}s.")


def notificar_balance_lote(
    callback_log: Callable[[str], None] | None,
    n_lote: int,
    evaluadas: int,
    esperadas: int,
) -> None:
    """Alerta de forma garantizada si el LLM omitio responder alguna fila del lote."""
    if callback_log and evaluadas < esperadas:
        omitidas = esperadas - evaluadas
        callback_log(
            f"[ALERTA] Lote {n_lote} evaluó {evaluadas}/{esperadas} filas "
            f"(IA omitió {omitidas})."
        )


def notificar_reintento_lote(
    callback_log: Callable[[str], None] | None,
    n_lote: int,
    intento: int,
    max_intentos: int,
) -> None:
    """Alerta reintento cuando un lote devolvio 0 filas evaluadas."""
    if callback_log:
        callback_log(
            f"[ALERTA] Lote {n_lote} devolvió 0 filas evaluadas. "
            f"Reintentando lote ({intento}/{max_intentos})..."
        )


def notificar_limite_cuota(
    callback_log: Callable[[str], None] | None,
    motor: str,
    n_lote: int,
    intento: int,
    max_intentos: int,
) -> None:
    """Informa al usuario que se detecto saturacion de cuota y se reiniciara perfil."""
    if callback_log:
        callback_log(
            f"[ALERTA] Límite de IA en {motor}. "
            f"Reiniciando perfil para Lote {n_lote} (intento {intento}/{max_intentos})..."
        )


def notificar_limite_persistente(
    callback_log: Callable[[str], None] | None, max_intentos: int
) -> None:
    """Informa cancelacion por agotamiento de reintentos de cuota."""
    if callback_log:
        callback_log(
            f"[ERROR] Límite persistente tras {max_intentos} reinicios. Deteniendo proceso."
        )


def notificar_cierre_exitoso(
    callback_log: Callable[[str], None] | None,
    ruta_salida: Path | None,
    ruta_md: Path | None = None,
) -> None:
    """Notifica rutas absolutas y confirmacion del guardado final."""
    if not callback_log:
        return
    if ruta_salida and ruta_salida.exists():
        callback_log(f"[OK] Guardado en CSV: {ruta_salida.resolve()}")
    if ruta_md and ruta_md.exists():
        callback_log(f"[OK] Bitácora de inspección guardada en: {ruta_md.resolve()}")


def notificar_cancelacion_proceso(
    callback_log: Callable[[str], None] | None,
    ruta_salida: Path | None = None,
) -> None:
    """Notifica cancelacion segura preservando avances."""
    if not callback_log:
        return
    if ruta_salida and ruta_salida.exists():
        callback_log(f"[INFO] Tarea cancelada. Avance salvaguardado en: {ruta_salida.resolve()}")
    else:
        callback_log("[INFO] Tarea cancelada por el usuario.")
