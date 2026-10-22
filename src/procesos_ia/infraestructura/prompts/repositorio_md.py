"""Repositorio de plantillas de prompts almacenadas en archivos Markdown (.md)."""

from __future__ import annotations

from pathlib import Path

from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.dominio.prompts import PlantillaPrompt


class RepositorioPromptsMd:
    """Implementa RepositorioPromptsProtocol persistiendo en archivos .md legibles."""

    def __init__(self, directorio_prompts: Path) -> None:
        self._directorio = directorio_prompts
        self._directorio.mkdir(parents=True, exist_ok=True)

    @property
    def directorio(self) -> Path:
        return self._directorio

    def guardar(self, plantilla: PlantillaPrompt) -> Path:
        """Guarda la plantilla en formato Markdown con cabecera de metadatos."""
        ruta_archivo = self._ruta_archivo(plantilla.identificador)

        lineas = [
            "---",
            f"id: {plantilla.identificador}",
            f"titulo: {plantilla.titulo}",
            f"descripcion: {plantilla.descripcion}",
            f"categoria: {plantilla.categoria}",
            f"columnas_requeridas: {', '.join(plantilla.columnas_requeridas)}",
            f"columnas_salida: {', '.join(plantilla.columnas_salida)}",
            f"version: {plantilla.version}",
            f"creado_en_utc: {plantilla.creado_en_utc}",
            "---",
            plantilla.contenido.strip(),
            "",
        ]

        contenido = "\n".join(lineas)
        ruta_archivo.write_text(contenido, encoding="utf-8")
        return ruta_archivo

    def obtener_por_id(self, identificador: str) -> PlantillaPrompt | None:
        """Lee y deserializa un archivo .md recuperando metadatos y cuerpo."""
        slug = PlantillaPrompt.normalizar_identificador(identificador)
        ruta = self._ruta_archivo(slug)
        if not ruta.is_file():
            return None

        texto = ruta.read_text(encoding="utf-8")
        return self._parsear_markdown(slug, texto)

    def listar_todos(self) -> list[PlantillaPrompt]:
        """Carga todas las plantillas .md disponibles en el directorio."""
        plantillas: list[PlantillaPrompt] = []
        for ruta in sorted(self._directorio.glob("*.md")):
            slug = ruta.stem
            texto = ruta.read_text(encoding="utf-8")
            parsed = self._parsear_markdown(slug, texto)
            if parsed is not None:
                plantillas.append(parsed)
        return plantillas

    def eliminar(self, identificador: str) -> bool:
        """Elimina el archivo .md si existe."""
        slug = PlantillaPrompt.normalizar_identificador(identificador)
        ruta = self._ruta_archivo(slug)
        if ruta.is_file():
            ruta.unlink()
            return True
        return False

    def _ruta_archivo(self, identificador: str) -> Path:
        return self._directorio / f"{identificador}.md"

    @staticmethod
    def _parsear_markdown(slug: str, texto: str) -> PlantillaPrompt | None:
        if not texto.startswith("---"):
            return None

        partes = texto.split("---", 2)
        if len(partes) < 3:
            return None

        metadatos_raw = partes[1].strip().splitlines()
        contenido = partes[2].strip()

        meta: dict[str, str] = {}
        for linea in metadatos_raw:
            if ":" in linea:
                clave, _, valor = linea.partition(":")
                meta[clave.strip()] = valor.strip()

        def parsear_lista(cadena: str) -> tuple[str, ...]:
            if not cadena:
                return ()
            return tuple(c.strip() for c in cadena.split(",") if c.strip())

        try:
            version = int(meta.get("version", "1"))
        except ValueError:
            version = 1

        return PlantillaPrompt(
            identificador=meta.get("id", slug),
            titulo=meta.get("titulo", slug),
            descripcion=meta.get("descripcion", ""),
            categoria=meta.get("categoria", "General"),
            contenido=contenido,
            columnas_requeridas=parsear_lista(meta.get("columnas_requeridas", "")),
            columnas_salida=parsear_lista(meta.get("columnas_salida", "")),
            creado_en_utc=meta.get("creado_en_utc", ""),
            version=version,
        )
