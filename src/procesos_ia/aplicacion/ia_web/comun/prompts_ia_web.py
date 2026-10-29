"""Definicion y sembrado de plantillas especializadas para IA Web con delimitador '|'."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from procesos_ia.dominio.evaluaciones import DefinicionResultado
from procesos_ia.dominio.prompts import PlantillaPrompt

if TYPE_CHECKING:
    from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts

logger = logging.getLogger(__name__)

CATEGORIA_IA_WEB = "ia_web"

AYUDA_DELIMITADOR_COLUMNAS = (
    "ESTRUCTURA DE ENTRADA:\n"
    "1. Delimitador de filas: Cada fila/registro esta en una linea separada precedida por '[FILA <id>]:'.\n"
    "2. Delimitador de columnas: Dentro de cada fila, las columnas estan delimitadas por ' | '.\n"
    "Usa esta estructura para distinguir exactamente donde termina cada columna y donde cambia de fila."
)

PLANTILLAS_POR_DEFECTO_WEB: tuple[dict, ...] = (
    {
        "identificador": "ia_web_evaluacion_multicelda",
        "titulo": "Evaluación Multi-Columna IA Web",
        "categoria": CATEGORIA_IA_WEB,
        "descripcion": "Plantilla general para evaluar varias celdas/columnas delimitadas con '|' en DeepSeek, Gemini y Modo IA.",
        "contenido": (
            "Analiza detenidamente la información proporcionada para cada registro.\n"
            f"{AYUDA_DELIMITADOR_COLUMNAS}\n\n"
            "INSTRUCCIONES:\n"
            "1. Evalúa la información según el objetivo requerido.\n"
            "2. Clasifica y valida la coherencia entre los campos del registro.\n"
            "3. Responde estrictamente en formato JSON con la clave 'resultados'."
        ),
        "resultados": (
            DefinicionResultado(
                clave="calificacion",
                criterio="Evaluación integral del registro",
                entradas=("datos",),
                tipo="texto",
                opciones=("Aceptable", "Observado", "Descartado"),
            ),
            DefinicionResultado(
                clave="motivo",
                criterio="Justificación de la evaluación",
                entradas=("datos",),
                tipo="texto",
                opciones=(),
            ),
        ),
    },
    {
        "identificador": "ia_web_calificacion_leads",
        "titulo": "Calificación de Leads IA Web",
        "categoria": CATEGORIA_IA_WEB,
        "descripcion": "Clasifica prospectos y leads evaluando campos de contacto y actividad separados por '|'.",
        "contenido": (
            "Evalúa el siguiente lote de prospectos (leads) comerciales.\n"
            f"{AYUDA_DELIMITADOR_COLUMNAS}\n\n"
            "OBJETIVOS:\n"
            "- Determinar si cuenta con nombre y teléfono o datos de contacto válidos.\n"
            "- Asignar prioridad de seguimiento: Alta, Media o Baja.\n"
            "- Resumir el rubro o servicio que ofrece.\n"
            "Responde únicamente en formato JSON con la estructura:\n"
            '{"resultados": [{"id": ..., "prioridad": "Alta|Media|Baja", "rubro": "...", "motivo": "..."}]}'
        ),
        "resultados": (
            DefinicionResultado(
                clave="prioridad",
                criterio="Prioridad de contacto comercial",
                entradas=("datos",),
                tipo="texto",
                opciones=("Alta", "Media", "Baja"),
            ),
            DefinicionResultado(
                clave="rubro",
                criterio="Actividad comercial detectada",
                entradas=("datos",),
                tipo="texto",
                opciones=(),
            ),
        ),
    },
    {
        "identificador": "ia_web_extraccion_datos",
        "titulo": "Extracción de Ficha Comercial IA Web",
        "categoria": CATEGORIA_IA_WEB,
        "descripcion": "Extrae entidades estructuradas (dueño, empresa, teléfono, ubicación) desde filas tabulares con '|'.",
        "contenido": (
            "Extrae la ficha comercial de cada registro recibido.\n"
            f"{AYUDA_DELIMITADOR_COLUMNAS}\n\n"
            "CAMPOS A EXTRAER:\n"
            "- propietario: Nombre del dueño o persona de contacto.\n"
            "- negocio: Nombre de la empresa o negocio comercial.\n"
            "- categoria: Actividades y servicios que realiza.\n"
            "- telefono: Número de contacto detectado.\n"
            "- ubicacion: Ciudad o estado donde opera.\n"
            "Responde estrictamente en formato JSON con la clave 'resultados'."
        ),
        "resultados": (
            DefinicionResultado(
                clave="propietario",
                criterio="Nombre del dueño o persona de contacto",
                entradas=("datos",),
                tipo="texto",
                opciones=(),
            ),
            DefinicionResultado(
                clave="negocio",
                criterio="Nombre comercial del negocio",
                entradas=("datos",),
                tipo="texto",
                opciones=(),
            ),
        ),
    },
)


def asegurar_plantillas_ia_web(
    servicio_prompts: ServicioCatalogoPrompts,
) -> list[PlantillaPrompt]:
    """Siembra las plantillas predeterminadas de IA Web si no existen en el catálogo."""
    plantillas_web = servicio_prompts.listar_plantillas(categoria=CATEGORIA_IA_WEB)
    ids_existentes = {p.identificador for p in plantillas_web}
    creadas: list[PlantillaPrompt] = []

    for def_p in PLANTILLAS_POR_DEFECTO_WEB:
        if def_p["identificador"] not in ids_existentes:
            try:
                plantilla = servicio_prompts.crear_plantilla(
                    titulo=def_p["titulo"],
                    contenido=def_p["contenido"],
                    categoria=def_p["categoria"],
                    descripcion=def_p["descripcion"],
                    identificador=def_p["identificador"],
                    resultados=def_p["resultados"],
                )
                creadas.append(plantilla)
                logger.info("[OK] Plantilla IA Web creada: %s", plantilla.titulo)
            except Exception as error:
                logger.warning(
                    "[ALERTA] No se pudo sembrar plantilla IA Web '%s': %s",
                    def_p["identificador"],
                    error,
                )

    return servicio_prompts.listar_plantillas(categoria=CATEGORIA_IA_WEB)


def poblar_combo_plantillas_ia_web(combo: object, servicio_prompts: object = None) -> None:
    """Rellena un QComboBox con las plantillas de categoria ia_web."""
    combo.clear(); combo.addItem("(Escribir prompt personalizado...)", "")
    try:
        if servicio_prompts is None:
            from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
            from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
            from procesos_ia.infraestructura.prompts.repositorio_md import RepositorioPromptsMd
            servicio_prompts = ServicioCatalogoPrompts(RepositorioPromptsMd(EnrutadorSalidas().plantillas))
        asegurar_plantillas_ia_web(servicio_prompts)
        for p in servicio_prompts.listar_plantillas(categoria=CATEGORIA_IA_WEB):
            combo.addItem(p.titulo, p.contenido)
    except Exception as error:
        logger.warning("[ALERTA] No se pudieron cargar plantillas IA Web: %s", error)
