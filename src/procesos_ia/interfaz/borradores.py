"""Gestor en memoria de borradores temporales para navegación fluida sin pérdida de datos."""

from __future__ import annotations

from typing import Any


def volcar_datos_editor(tabla: Any) -> list[dict[str, Any]]:
    """Extrae las filas del editor de resultados como lista de diccionarios planos."""
    datos: list[dict[str, Any]] = []
    for fila in range(tabla.rowCount()):
        valores = [tabla.item(fila, col).text().strip() for col in range(tabla.columnCount())]
        datos.append({
            "clave": valores[0],
            "criterio": valores[1],
            "entradas": [e.strip() for e in valores[2].split(",") if e.strip()],
            "tipo": tabla.cellWidget(fila, 3).currentText(),
            "opciones": [e.strip() for e in valores[4].split("|") if e.strip()],
        })
    return datos


class GestorBorradores:
    """Conserva el estado en curso de las vistas secundarias con costo mínimo (< 50 KB)."""

    def __init__(self) -> None:
        self._borrador_prompts: dict[str, Any] = {}
        self._borrador_preparacion: dict[str, Any] = {}

    def guardar_prompts(
        self,
        titulo: str,
        categoria: str,
        descripcion: str,
        contenido: str,
        resultados_datos: list[dict[str, Any]],
        identificador_activo: str | None = None,
    ) -> None:
        self._borrador_prompts = {
            "titulo": titulo,
            "categoria": categoria,
            "descripcion": descripcion,
            "contenido": contenido,
            "resultados_datos": [dict(r) for r in resultados_datos],
            "identificador_activo": identificador_activo,
        }

    def obtener_prompts(self) -> dict[str, Any]:
        return dict(self._borrador_prompts)

    def tiene_borrador_prompts(self) -> bool:
        return bool(self._borrador_prompts)

    def limpiar_prompts(self) -> None:
        self._borrador_prompts.clear()

    def guardar_preparacion(
        self,
        asignaciones_entradas: dict[str, list[str]],
        destinos_salidas: dict[str, str],
        identificador_plantilla: str = "",
    ) -> None:
        self._borrador_preparacion = {
            "asignaciones_entradas": {k: list(v) for k, v in asignaciones_entradas.items()},
            "destinos_salidas": dict(destinos_salidas),
            "identificador_plantilla": identificador_plantilla,
        }

    def obtener_preparacion(self) -> dict[str, Any]:
        return dict(self._borrador_preparacion)

    def tiene_borrador_preparacion(self) -> bool:
        return bool(self._borrador_preparacion)

    def limpiar_preparacion(self) -> None:
        self._borrador_preparacion.clear()
