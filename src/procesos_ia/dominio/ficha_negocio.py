"""Entidad de dominio para almacenar y estructurar datos de ficha comercial extraidos."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from procesos_ia.dominio.normalizador import normalizar_texto


@dataclass(slots=True)
class FichaNegocioLens:
    """Representa la informacion comercial y de contacto identificada por Google Lens."""

    id_registro: str = ""
    propietario: str = ""
    negocio: str = ""
    categoria: str = ""
    telefono: str = ""
    ubicacion: str = ""
    licencia: str = ""
    correo_electronico: str = ""
    sitio_web: str = ""
    idiomas: str = ""
    estado_ia: str = ""
    enlaces: list[str] = field(default_factory=list)
    texto_sintesis: str = ""
    fuente_imagen: str = ""
    metadatos_adicionales: dict[str, Any] = field(default_factory=dict)

    def normalizar(self) -> FichaNegocioLens:
        """Aplica saneamiento de caracteres y espaciado a los campos de texto."""
        def limpiar(txt: str) -> str:
            t = re.sub(r"\[(?:Image|Imagen)\s*:\s*\d+\]", "", txt or "", flags=re.IGNORECASE)
            return normalizar_texto(t)

        self.propietario = limpiar(self.propietario)
        self.negocio = limpiar(self.negocio)
        self.categoria = limpiar(self.categoria)
        if self.telefono:
            tel = re.sub(r"[\r\n]+", " / ", self.telefono)
            tel = re.sub(r"\s*/\s*", " / ", tel).strip(" /")
            self.telefono = limpiar(tel)
        else:
            self.telefono = ""
        self.ubicacion = limpiar(self.ubicacion)
        self.licencia = limpiar(self.licencia)
        self.correo_electronico = limpiar(self.correo_electronico)
        self.sitio_web = limpiar(self.sitio_web)
        self.idiomas = limpiar(self.idiomas)
        self.estado_ia = normalizar_texto(self.estado_ia)
        self.texto_sintesis = normalizar_texto(self.texto_sintesis)
        return self

    def a_diccionario(self, normalizado: bool = True) -> dict[str, Any]:
        """Convierte la entidad a diccionario compatible con exportacion tabular y JSON."""
        if normalizado:
            self.normalizar()
        datos = asdict(self)
        datos["enlaces_str"] = " ; ".join(self.enlaces)
        return datos

    @classmethod
    def desde_diccionario(cls, datos: dict[str, Any]) -> FichaNegocioLens:
        """Crea una instancia a partir de un diccionario arbitrario de entrada."""
        enlaces_raw = datos.get("enlaces", [])
        if isinstance(enlaces_raw, str):
            enlaces = [e.strip() for e in enlaces_raw.split(";") if e.strip()]
        else:
            enlaces = list(enlaces_raw)

        return cls(
            id_registro=str(datos.get("id_registro", "")),
            propietario=str(datos.get("propietario", "")),
            negocio=str(datos.get("negocio", "")),
            categoria=str(datos.get("categoria", "")),
            telefono=str(datos.get("telefono", "")),
            ubicacion=str(datos.get("ubicacion", "")),
            licencia=str(datos.get("licencia", "")),
            correo_electronico=str(datos.get("correo_electronico", "")),
            sitio_web=str(datos.get("sitio_web", "")),
            idiomas=str(datos.get("idiomas", "")),
            estado_ia=str(datos.get("estado_ia", "")),
            enlaces=enlaces,
            texto_sintesis=str(datos.get("texto_sintesis", "")),
            fuente_imagen=str(datos.get("fuente_imagen", "")),
            metadatos_adicionales=dict(datos.get("metadatos_adicionales", {})),
        )
