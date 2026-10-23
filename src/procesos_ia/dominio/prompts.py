"""Entidades de dominio para plantillas de prompts y refinamiento asistido."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from procesos_ia.dominio.evaluaciones import DefinicionResultado


@dataclass(frozen=True, slots=True)
class PlantillaPrompt:
    """Plantilla de instrucciones para el modelo con metadatos de clasificación."""

    identificador: str
    titulo: str
    descripcion: str
    categoria: str
    contenido: str
    columnas_requeridas: tuple[str, ...] = field(default_factory=tuple)
    columnas_salida: tuple[str, ...] = field(default_factory=tuple)
    creado_en_utc: str = ""
    version: int = 1
    resultados: tuple[DefinicionResultado, ...] = field(default_factory=tuple)

    @classmethod
    def normalizar_identificador(cls, texto: str) -> str:
        """Genera un slug seguro para nombres de archivo en disco."""
        limpio = re.sub(r"[^\w\s-]", "", texto.lower().strip())
        slug = re.sub(r"[-\s]+", "_", limpio)
        return slug or "prompt_sin_nombre"


@dataclass(frozen=True, slots=True)
class PeticionRefinamiento:
    """Datos de entrada proporcionados por el usuario para refinar su instrucción."""

    idea_usuario: str
    columnas_entrada: tuple[str, ...] = field(default_factory=tuple)
    ejemplo_fila: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResultadoRefinamiento:
    """Resultado del metaprompt con la instrucción optimizada para el LLM."""

    prompt_refinado: str
    columnas_salida_sugeridas: tuple[str, ...]
    explicacion_resumen: str
    resultados: tuple[DefinicionResultado, ...] = field(default_factory=tuple)
