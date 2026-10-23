"""Plantillas portables, refinamiento sin encabezados y reanudacion compatible."""

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
from procesos_ia.dominio.evaluaciones import DefinicionResultado, resultados_compatibles
from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.dominio.modelos import ConfiguracionTrabajo
from procesos_ia.dominio.prompts import PeticionRefinamiento
from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.persistencia.identidad_trabajo import IdentidadTrabajo
from procesos_ia.infraestructura.prompts.refinador_ollama import RefinadorPromptOllama
from procesos_ia.infraestructura.prompts.repositorio_md import RepositorioPromptsMd


class PruebaPlantillasEvaluacion(unittest.TestCase):
    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.raiz = Path(self.temporal.name)
        self.repo = RepositorioPromptsMd(self.raiz / "prompts")
        self.catalogo = ServicioCatalogoPrompts(self.repo)
        self.resultado = DefinicionResultado(
            "idioma", "Determinar idioma --- con evidencia", ("texto",),
            "texto", ("espanol", "otro", "indeterminado"),
        )

    def test_persistencia_conserva_definiciones_y_versiona_edicion(self) -> None:
        primera = self.catalogo.crear_plantilla("Idioma", "Evalua texto", resultados=(self.resultado,))
        recuperada = self.catalogo.obtener_plantilla(primera.identificador)
        self.assertEqual(recuperada.resultados, (self.resultado,))
        segunda = self.catalogo.crear_plantilla(
            "Idioma", "Otro criterio", identificador=primera.identificador,
            resultados=(self.resultado,),
        )
        self.assertEqual(segunda.version, primera.version + 1)
        self.assertEqual(segunda.creado_en_utc, primera.creado_en_utc)

    def test_plantilla_antigua_se_lee_sin_reescribir(self) -> None:
        archivo = self.repo.directorio / "anterior.md"
        contenido = "---\nid: anterior\ntitulo: Anterior\ncolumnas_salida: categoria\n---\nClasifica actividad\n"
        archivo.write_text(contenido, encoding="utf-8")
        plantilla = self.repo.obtener_por_id("anterior")
        self.assertEqual(resultados_compatibles(plantilla)[0].clave, "categoria")
        self.assertEqual(archivo.read_text(encoding="utf-8"), contenido)

    def test_refinador_no_envia_columnas_ni_ejemplos_del_archivo(self) -> None:
        cliente = MagicMock(spec=ClienteHttpOllama)
        cliente.generar_estructurado.return_value = {
            "prompt_refinado": "Evalua el idioma del texto con evidencia suficiente.",
            "resultados": [{
                "clave": "idioma", "criterio": "Idioma observado", "entradas": ["texto"],
                "tipo": "texto", "opciones": ["espanol", "otro", "indeterminado"],
            }],
            "explicacion": "Criterios revisables",
        }
        refinador = RefinadorPromptOllama(cliente)
        resultado = refinador.refinar_prompt(PeticionRefinamiento(
            "Evaluar idioma", ("columna_privada",), {"columna_privada": "secreto"},
        ), "simulado")
        argumentos = cliente.generar_estructurado.call_args.kwargs
        self.assertEqual(json.loads(argumentos["prompt"]), {"intencion": "Evaluar idioma"})
        self.assertNotIn("columna_privada", argumentos["prompt"])
        self.assertNotIn("secreto", argumentos["prompt"])
        self.assertIn("No solicites", argumentos["sistema"])
        self.assertIn("resultados", argumentos["esquema_salida"]["required"])
        self.assertEqual(resultado.resultados[0].entradas, ("texto",))

    def test_refinador_normaliza_claves_con_espacios_y_tildes(self) -> None:
        cliente = MagicMock(spec=ClienteHttpOllama)
        cliente.generar_estructurado.return_value = {
            "prompt_refinado": "Clasifica segun el tipo de cliente.",
            "resultados": [{
                "clave": "tipo de cliente (categoría)", "criterio": "Clasifica cliente",
                "entradas": ["texto"], "tipo": "texto", "opciones": [],
            }],
            "explicacion": "Normaliza clave",
        }
        refinado = RefinadorPromptOllama(cliente).refinar_prompt(
            PeticionRefinamiento("clasificar"), "simulado",
        )
        self.assertEqual(refinado.resultados[0].clave, "tipo_de_cliente_categoria")

    def test_refinador_sanea_booleano_con_opciones_y_duplicados(self) -> None:
        cliente = MagicMock(spec=ClienteHttpOllama)
        cliente.generar_estructurado.return_value = {
            "prompt_refinado": "Determina si el nombre es latino.",
            "resultados": [{
                "clave": "es_latino", "criterio": "Nombre latino",
                "entradas": ["datos"], "tipo": "booleano", "opciones": ["si", "no", "SI"],
            }],
            "explicacion": "Sanea tipo booleano con opciones categoriales",
        }
        refinado = RefinadorPromptOllama(cliente).refinar_prompt(
            PeticionRefinamiento("es latino"), "simulado",
        )
        res = refinado.resultados[0]
        self.assertEqual(res.tipo, "texto")
        self.assertEqual(res.opciones, ("si", "no"))

    def test_resultados_invalidos_no_se_guardan(self) -> None:
        for resultado in (
            replace(self.resultado, tipo="codigo"),
            replace(self.resultado, clave="estado_ia"),
            replace(self.resultado, entradas=()),
        ):
            with self.subTest(resultado=resultado), self.assertRaises(ErrorProcesamiento):
                self.catalogo.crear_plantilla("Invalida", "Evalua", resultados=(resultado,))
        self.assertEqual(list(self.repo.directorio.glob("*.md")), [])

    def _configuracion(self) -> ConfiguracionTrabajo:
        origen = self.raiz / "origen.csv"
        origen.write_text("texto\nHola\n", encoding="utf-8")
        return ConfiguracionTrabajo(
            origen, self.raiz / "salida", "simulado", 1, 1000, 512, 0.0, 10.0,
            ("texto",), "Evalua idioma", "csv", ("idioma_ia",),
        )

    def test_no_mezcla_trabajos_con_otro_prompt_o_modelo(self) -> None:
        config = self._configuracion()
        config.directorio_salida.mkdir()
        identidad = IdentidadTrabajo(config)
        identidad.vincular(config.directorio_salida, False)
        IdentidadTrabajo(config).vincular(config.directorio_salida, True)
        for cambio in ({"prompt_sistema": "Otra tarea"}, {"nombre_modelo": "otro"},
                       {"columnas_salida_modelo": ("otra_ia",)}):
            with self.subTest(cambio=cambio), self.assertRaises(ErrorProcesamiento):
                IdentidadTrabajo(replace(config, **cambio)).vincular(config.directorio_salida, True)

    def test_rechaza_progreso_antiguo_sin_identidad(self) -> None:
        config = self._configuracion()
        config.directorio_salida.mkdir()
        with self.assertRaisesRegex(ErrorProcesamiento, "no tiene identidad"):
            IdentidadTrabajo(config).vincular(config.directorio_salida, True)

    def test_detecta_origen_modificado_durante_trabajo(self) -> None:
        config = self._configuracion()
        identidad = IdentidadTrabajo(config)
        config.ruta_entrada.write_text("texto\nCambio de origen\n", encoding="utf-8")
        with self.assertRaisesRegex(ErrorProcesamiento, "origen cambio"):
            identidad.verificar_origen()
