"""Correlacion de respuestas del modelo con las filas enviadas, sin persistencia."""

import re
from typing import Any

from procesos_ia.aplicacion.comun.gestor_reanudacion_base import (
    COLUMNA_ESTADO, COLUMNA_FECHA, COLUMNA_ID, COLUMNA_MOTIVO, GestorReanudacionBase,
)
from procesos_ia.aplicacion.comun.identidad_tabular import parametros_tabulares
from procesos_ia.aplicacion.ia_web.comun.gestor_resiliencia_web import filtrar_lineas_datos_ia
from procesos_ia.dominio.normalizador import sanear_identificador_columna
from procesos_ia.dominio.reanudacion import EstadoIA


def _expandir_texto_a_dict(val: str) -> dict[str, Any]:
    """Convierte texto plano en diccionario, separando columnas por '|' si hay multiples."""
    limpio = val.strip()
    if "|" in limpio:
        partes = [p.strip() for p in limpio.split("|") if p.strip()]
        if len(partes) >= 2:
            salida: dict[str, Any] = {"evaluacion_ia": limpio}
            for idx, parte in enumerate(partes, start=1):
                salida[f"evaluacion_col_{idx}"] = parte
            return salida
    return {"evaluacion_ia": limpio}


def mapear_respuestas_lote(
    texto_resp: str,
    datos: Any,
    lote_actual: list[dict[str, Any]],
    indice_base: int = 1,
) -> list[dict[str, Any]]:
    """Empareja inteligentemente las respuestas de la IA (del 1 al N del lote) con las filas originales."""
    items: list[Any] = []
    tiene_estructura = isinstance(datos, (dict, list)) and bool(datos)
    if isinstance(datos, dict):
        res = datos.get("resultados") or datos.get("resultado", [])
        if not res and any(clave in datos for clave in ("id", "ID", "fila")):
            res = [datos]
        items = res if isinstance(res, list) else [res]
    elif isinstance(datos, list):
        items = datos

    mapa: dict[int, dict[str, Any]] = {}
    tamano = len(lote_actual)

    def _resolver(n: int) -> int | None:
        return (n - 1) if (1 <= n <= tamano) else ((n - indice_base) if (indice_base <= n < indice_base + tamano) else None)

    for idx_item, it in enumerate(items):
        if isinstance(it, dict):
            id_val = next((it[k] for k in ("id", "ID", "fila") if k in it), None)
            if isinstance(id_val, bool):
                continue
            try:
                id_num = int(id_val) if id_val is not None else (idx_item + 1)
            except (ValueError, TypeError):
                continue
            pos = _resolver(id_num)
            if pos is not None:
                if pos in mapa:
                    raise ValueError(parametros_tabulares()["error_respuesta"])
                mapa[pos] = {sanear_identificador_columna(k, "col"): v for k, v in it.items() if k.lower() not in ("id", "fila")}
        elif isinstance(it, str) and idx_item < tamano:
            mapa[idx_item] = {"evaluacion_ia": it.strip()}

    tiene_etiquetas = False
    if not mapa and texto_resp and not tiene_estructura:
        for linea in texto_resp.splitlines():
            lin = linea.strip()
            if not lin:
                continue
            m = re.match(r"^(?:\[?FILA\s*(\d+)\]?|(\d+)[\.\)\:\-])\s*[:\.\-]?\s*(.*)", lin, re.I)
            if m:
                tiene_etiquetas = True
                id_num = int(m.group(1) or m.group(2))
                val = (m.group(3) or "").strip().lstrip(":-. ")
                pos = _resolver(id_num)
                if pos is not None:
                    if pos in mapa:
                        raise ValueError(parametros_tabulares()["error_respuesta"])
                    mapa[pos] = _expandir_texto_a_dict(val)

    if not mapa and texto_resp and not tiene_estructura and not tiene_etiquetas:
        for sub_i, lin in enumerate(filtrar_lineas_datos_ia(texto_resp, max_filas=tamano)):
            mapa[sub_i] = _expandir_texto_a_dict(lin)

    filas_enriquecidas = []
    fecha_iso = GestorReanudacionBase.fecha_actual_iso()
    for idx, f in enumerate(lote_actual):
        f_res = dict(f)
        claves_entrada: dict[str, str] = {}
        for c in f.keys():
            if c in (COLUMNA_ID, COLUMNA_ESTADO):
                break
            claves_entrada[str(c).casefold()] = str(c)
        eval_dict = mapa.get(idx)
        if eval_dict and any(v not in (None, "") for v in eval_dict.values()):
            for k, v in eval_dict.items():
                clave_dest = k
                if clave_dest.casefold() in claves_entrada and not clave_dest.casefold().endswith("_ia"):
                    base_ia = f"{clave_dest}_ia"
                    clave_dest = base_ia
                    suf = 2
                    while clave_dest.casefold() in claves_entrada:
                        clave_dest = f"{base_ia}_{suf}"
                        suf += 1
                f_res[clave_dest] = v
            f_res.pop("error_inferencia", None)
            f_res.pop("respuesta_modelo", None)
            if COLUMNA_ID in f:
                f_res[COLUMNA_ID] = f[COLUMNA_ID]
            f_res[COLUMNA_ESTADO] = EstadoIA.EXITOSO.value
            f_res[COLUMNA_MOTIVO] = "[OK] Evaluado"
        else:
            f_res[COLUMNA_ESTADO] = EstadoIA.OMITIDO.value
            f_res[COLUMNA_MOTIVO] = "[ALERTA] No devuelto por LLM en este lote"
        f_res[COLUMNA_FECHA] = fecha_iso
        filas_enriquecidas.append(f_res)
    return filas_enriquecidas

