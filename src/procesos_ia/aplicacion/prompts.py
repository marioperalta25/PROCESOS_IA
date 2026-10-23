"""Casos de uso y contratos de aplicación para el catálogo y refinamiento de prompts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.dominio.evaluaciones import DefinicionResultado
from procesos_ia.dominio.prompts import (
    PeticionRefinamiento,
    PlantillaPrompt,
    ResultadoRefinamiento,
)


class RepositorioPromptsProtocol(Protocol):
    """Contrato para persistencia de plantillas en archivos locales Markdown (.md)."""

    def guardar(self, plantilla: PlantillaPrompt) -> Path:
        """Persiste la plantilla en disco y retorna la ruta del archivo generado."""
        ...

    def obtener_por_id(self, identificador: str) -> PlantillaPrompt | None:
        """Carga una plantilla por su identificador único."""
        ...

    def listar_todos(self) -> list[PlantillaPrompt]:
        """Recupera la lista completa de plantillas almacenadas."""
        ...

    def eliminar(self, identificador: str) -> bool:
        """Elimina el archivo de la plantilla en disco."""
        ...


class MotorRefinamientoProtocol(Protocol):
    """Contrato para solicitar al modelo local la optimización de un prompt."""

    def refinar_prompt(
        self,
        peticion: PeticionRefinamiento,
        nombre_modelo: str,
    ) -> ResultadoRefinamiento:
        """Transforma la idea del usuario en un prompt estructurado de alta precisión."""
        ...


class ServicioCatalogoPrompts:
    """Caso de uso para gestionar el ciclo de vida del catálogo y su refinamiento."""

    def __init__(
        self,
        repositorio: RepositorioPromptsProtocol,
        motor_refinamiento: MotorRefinamientoProtocol | None = None,
    ) -> None:
        self._repo = repositorio
        self._refinador = motor_refinamiento

    def crear_plantilla(
        self,
        titulo: str,
        contenido: str,
        categoria: str = "General",
        descripcion: str = "",
        columnas_requeridas: tuple[str, ...] = (),
        columnas_salida: tuple[str, ...] = (),
        identificador: str | None = None,
        resultados: tuple[DefinicionResultado, ...] = (),
    ) -> PlantillaPrompt:
        """Valida y guarda una nueva plantilla en el catálogo local."""
        if not titulo.strip():
            raise ErrorProcesamiento("El titulo de la plantilla no puede estar vacio")
        if not contenido.strip():
            raise ErrorProcesamiento("El contenido del prompt no puede estar vacio")

        slug = identificador or PlantillaPrompt.normalizar_identificador(titulo)
        for resultado in resultados:
            resultado.validar()
        if len({r.clave for r in resultados}) != len(resultados):
            raise ErrorProcesamiento("Hay resultados duplicados")
        anterior = self._repo.obtener_por_id(slug)
        marca_tiempo = datetime.now(timezone.utc).isoformat()

        plantilla = PlantillaPrompt(
            identificador=slug,
            titulo=titulo.strip(),
            descripcion=descripcion.strip(),
            categoria=categoria.strip(),
            contenido=contenido.strip(),
            columnas_requeridas=columnas_requeridas,
            columnas_salida=columnas_salida,
            creado_en_utc=anterior.creado_en_utc if anterior else marca_tiempo,
            version=anterior.version + 1 if anterior else 1,
            resultados=resultados,
        )

        self._repo.guardar(plantilla)
        return plantilla

    def listar_plantillas(self, categoria: str | None = None) -> list[PlantillaPrompt]:
        """Devuelve las plantillas disponibles, opcionalmente filtradas por categoría."""
        todas = self._repo.listar_todos()
        if categoria is None:
            return todas
        cat_normalizada = categoria.strip().lower()
        return [p for p in todas if p.categoria.strip().lower() == cat_normalizada]

    def obtener_plantilla(self, identificador: str) -> PlantillaPrompt | None:
        return self._repo.obtener_por_id(identificador)

    def eliminar_plantilla(self, identificador: str) -> bool:
        return self._repo.eliminar(identificador)

    def refinar_idea(
        self,
        peticion: PeticionRefinamiento,
        nombre_modelo: str,
    ) -> ResultadoRefinamiento:
        """Envía la intención del usuario al motor para producir el prompt estructurado."""
        if self._refinador is None:
            raise ErrorProcesamiento("Motor de refinamiento no configurado en este entorno")
        if not peticion.idea_usuario.strip():
            raise ErrorProcesamiento("La descripcion de la tarea a realizar no puede estar vacia")

        return self._refinador.refinar_prompt(peticion, nombre_modelo)
