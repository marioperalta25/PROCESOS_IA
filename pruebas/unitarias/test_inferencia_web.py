"""Pruebas unitarias para la infraestructura de inferencia web y manipulación DOM."""

from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from procesos_ia.aplicacion.contratos import ServicioInferenciaProtocol
from procesos_ia.dominio.evaluaciones import ContratoEvaluacion, DefinicionResultado
from procesos_ia.dominio.modelos import ConfiguracionTrabajo, RegistroEntrada
from procesos_ia.infraestructura.web.configuracion_web import (
    ConfiguracionVentanaWeb,
    ConfiguracionWeb,
)
from procesos_ia.infraestructura.web.controlador_ventana import (
    buscar_manejador_ventana,
    es_plataforma_compatible,
)
from procesos_ia.infraestructura.web.extractor_json import (
    extraer_y_reparar_json,
)
from procesos_ia.infraestructura.web.servicio_inferencia_web import ServicioInferenciaWeb


class TestInferenciaWeb(unittest.TestCase):
    """Conjunto de pruebas para validar componentes de inferencia web."""

    def test_configuracion_web_crea_directorios_y_limpia_locks(self) -> None:
        with tempfile.TemporaryDirectory() as dir_temp:
            base = Path(dir_temp)
            cfg = ConfiguracionWeb(directorio_base=base)
            cfg.asegurar_directorios()

            self.assertTrue(cfg.directorio_perfil.exists())
            self.assertTrue(cfg.directorio_imagenes_temp.exists())

            # Crear archivo SingletonLock simulado
            lock = cfg.directorio_perfil / "SingletonLock"
            lock.touch()
            self.assertTrue(lock.exists())

            resultado_limpieza = cfg.limpiar_bloqueos_perfil()
            self.assertTrue(resultado_limpieza)
            self.assertFalse(lock.exists())

    def test_extraer_y_reparar_json_con_bloques_y_texto(self) -> None:
        # Caso 1: Bloque markdown estricto
        md_json = "```json\n{\n  \"calificacion\": \"si\",\n  \"confianza\": 95\n}\n```"
        res1 = extraer_y_reparar_json(md_json)
        self.assertIsNotNone(res1)
        self.assertEqual(res1.get("calificacion"), "si")
        self.assertEqual(res1.get("confianza"), 95)

        # Caso 2: Texto con llaves intermedias
        txt_llaves = "Resultado del analisis:\n{\"calificacion\": \"no\"}\nFin."
        res2 = extraer_y_reparar_json(txt_llaves)
        self.assertIsNotNone(res2)
        self.assertEqual(res2.get("calificacion"), "no")

        # Caso 3: Texto invalido
        res3 = extraer_y_reparar_json("no hay ningun json aqui")
        self.assertIsNone(res3)

    def test_controlador_ventana_plataforma(self) -> None:
        compatible = es_plataforma_compatible()
        self.assertIsInstance(compatible, bool)

    def test_servicio_inferencia_web_cumple_protocolo(self) -> None:
        servicio = ServicioInferenciaWeb(tipo_motor="gemini")
        self.assertTrue(hasattr(servicio, "procesar_lote"))
        self.assertTrue(callable(servicio.procesar_lote))

    @patch("procesos_ia.infraestructura.web.gestor_sesion_nodriver.GestorSesionNodriver.navegar_o_reutilizar")
    def test_servicio_inferencia_web_procesar_lote_con_mock(self, mock_navegar: MagicMock) -> None:
        async def mock_evaluar(script: str) -> Any:
            if "data-test-id=\"code-content\"" in script or "model-response-text" in script:
                return {"generando": False, "texto": '{"habla_espanol": "si"}', "es_codigo": True}
            if "button[aria-label*=\"Enviar\"]" in script or "sendBtn" in script:
                return True
            if "contenteditable" in script:
                return "OK"
            return None

        mock_pestana = AsyncMock()
        mock_pestana.evaluate = AsyncMock(side_effect=mock_evaluar)
        mock_navegar.return_value = mock_pestana

        from procesos_ia.dominio.evaluaciones import VinculoEntrada, VinculoSalida
        contrato = ContratoEvaluacion(
            resultados=(
                DefinicionResultado(
                    clave="habla_espanol",
                    criterio="Determina si habla espanol",
                    entradas=("datos",),
                    tipo="texto",
                    opciones=("si", "no"),
                ),
            ),
            entradas=(
                VinculoEntrada(entrada="datos", columnas=("texto",)),
            ),
            salidas=(
                VinculoSalida(resultado="habla_espanol", columna="habla_espanol"),
            ),
        )
        configuracion = ConfiguracionTrabajo(
            ruta_entrada=Path("entrada.csv"),
            directorio_salida=Path("salida"),
            nombre_modelo="gemini-web",
            tamano_lote=1,
            limite_filas_particion=1000,
            ventana_contexto=2048,
            temperatura=0.1,
            tiempo_limite_lote_segundos=30.0,
            columnas_evaluar=("texto",),
            prompt_sistema="Determina si habla espanol.",
            formato_salida="csv",
            columnas_salida_modelo=("habla_espanol",),
            contrato_evaluacion=contrato,
        )

        registro = RegistroEntrada(
            identificador="ID_101",
            indice_fila=1,
            valores_originales={"texto": "Hola mundo"},
            datos_para_modelo={"texto": "Hola mundo"},
        )

        cfg_web = ConfiguracionWeb(tiempo_estabilidad_segundos=0.01)
        servicio = ServicioInferenciaWeb(tipo_motor="gemini", configuracion_web=cfg_web)
        salidas = servicio.procesar_lote([registro], configuracion)

        self.assertEqual(len(salidas), 1)
        self.assertEqual(salidas[0]["identificador"], "ID_101")
        self.assertEqual(salidas[0]["habla_espanol"], "si")

    def test_detectar_ruta_imagen_con_carpeta_y_extensiones(self) -> None:
        servicio = ServicioInferenciaWeb(tipo_motor="gemini")
        with tempfile.TemporaryDirectory() as dir_temp:
            dir_imagenes = Path(dir_temp)
            img1 = dir_imagenes / "foto_cliente.jpg"
            img1.touch()
            img2 = dir_imagenes / "recibo_pago.png"
            img2.touch()

            # Caso 1: Ruta absoluta directa existente
            res1 = servicio._detectar_ruta_imagen({"archivo": str(img1)})
            self.assertEqual(res1, img1)

            # Caso 2: Solo nombre de archivo buscando en carpeta_imagenes
            res2 = servicio._detectar_ruta_imagen({"archivo": "recibo_pago.png"}, carpeta_imagenes=dir_imagenes)
            self.assertEqual(res2, img2)

            # Caso 3: Nombre sin extension buscando en carpeta_imagenes con extensiones candidatas
            res3 = servicio._detectar_ruta_imagen({"archivo": "foto_cliente"}, carpeta_imagenes=dir_imagenes)
            self.assertEqual(res3, img1)

            # Caso 4: Archivo no existente
            res4 = servicio._detectar_ruta_imagen({"archivo": "no_existe.jpg"}, carpeta_imagenes=dir_imagenes)
            self.assertIsNone(res4)

    def test_extraer_y_reparar_json_con_listas(self) -> None:
        md_lista = "```json\n[\n  {\"identificador\": \"ID_1\", \"val\": 10},\n  {\"identificador\": \"ID_2\", \"val\": 20}\n]\n```"
        res = extraer_y_reparar_json(md_lista)
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["identificador"], "ID_1")

    @patch("procesos_ia.infraestructura.web.gestor_sesion_nodriver.GestorSesionNodriver.navegar_o_reutilizar")
    def test_servicio_inferencia_web_lote_tabular_sin_imagenes(self, mock_navegar: MagicMock) -> None:
        async def mock_evaluar(script: str) -> Any:
            if any(s in script for s in ("ds-assistant-message-main-content", "model-response-text", "code-content")):
                resp = '[{"identificador": "ID_A", "habla_espanol": "si"}, {"identificador": "ID_B", "habla_espanol": "no"}]'
                return {"generando": False, "completo": True, "texto": resp, "es_codigo": True}
            return True

        mock_pestana = AsyncMock()
        mock_pestana.evaluate = AsyncMock(side_effect=mock_evaluar)
        mock_navegar.return_value = mock_pestana

        from procesos_ia.dominio.evaluaciones import VinculoEntrada, VinculoSalida
        contrato = ContratoEvaluacion(
            resultados=(DefinicionResultado(clave="habla_espanol", criterio="Determina idioma", opciones=("si", "no")),),
            entradas=(VinculoEntrada(entrada="datos", columnas=("texto",)),),
            salidas=(VinculoSalida(resultado="habla_espanol", columna="habla_espanol"),),
        )
        configuracion = ConfiguracionTrabajo(
            ruta_entrada=Path("entrada.csv"), directorio_salida=Path("salida"),
            nombre_modelo="deepseek-web", tamano_lote=2, limite_filas_particion=1000,
            ventana_contexto=2048, temperatura=0.1, tiempo_limite_lote_segundos=30.0,
            columnas_evaluar=("texto",), prompt_sistema="Determina si habla espanol.",
            formato_salida="csv", columnas_salida_modelo=("habla_espanol",),
            contrato_evaluacion=contrato, modo_procesamiento="lote",
        )
        reg_a = RegistroEntrada("ID_A", 1, {"texto": "Hola"}, {"texto": "Hola"})
        reg_b = RegistroEntrada("ID_B", 2, {"texto": "Hello"}, {"texto": "Hello"})

        servicio = ServicioInferenciaWeb(tipo_motor="deepseek", configuracion_web=ConfiguracionWeb(tiempo_estabilidad_segundos=0.01))
        salidas = servicio.procesar_lote([reg_a, reg_b], configuracion)

        self.assertEqual(len(salidas), 2)
        self.assertEqual(salidas[0]["identificador"], "ID_A")
        self.assertEqual(salidas[0]["habla_espanol"], "si")
        self.assertEqual(salidas[1]["identificador"], "ID_B")
        self.assertEqual(salidas[1]["habla_espanol"], "no")


if __name__ == "__main__":
    unittest.main()
