"""Pruebas unitarias para la interfaz gráfica de escritorio y sus componentes."""

from __future__ import annotations

import os
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

# Configurar plataforma offscreen para ejecucion de pruebas sin servidor X/pantalla grafica
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from procesos_ia.aplicacion.coordinador import CoordinadorTrabajo
from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
from procesos_ia.dominio.prompts import PlantillaPrompt
from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.ollama.cache_modelos import CacheModelosOllama
from procesos_ia.infraestructura.ollama.modelos import (
    DiagnosticoOllama,
    EstadoServicioOllama,
    InformacionModelo,
)
from procesos_ia.interfaz.app import crear_aplicacion
from procesos_ia.interfaz.componentes.panel_archivos import PanelArchivos
from procesos_ia.interfaz.componentes.panel_configuracion import PanelConfiguracionIA
from procesos_ia.interfaz.componentes.panel_controles import PanelControles
from procesos_ia.interfaz.componentes.panel_encabezado import PanelEncabezado
from procesos_ia.interfaz.componentes.panel_telemetria import PanelTelemetria
from procesos_ia.interfaz.hilos import HiloListarModelos
from procesos_ia.interfaz.recursos import GestorRecursos
from procesos_ia.interfaz.ventana_principal import VentanaPrincipal


class PruebaInterfazEscritorio(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = crear_aplicacion([])

    def test_gestor_recursos_carga_rutas_validas(self) -> None:
        gestor = GestorRecursos()
        self.assertTrue(gestor.ruta_icono_aplicacion.name.endswith(".ico"))
        self.assertTrue(gestor.ruta_emblema_dragon.name.endswith(".png"))

        icono = gestor.obtener_icono_aplicacion()
        self.assertFalse(icono.isNull())

        pix = gestor.obtener_pixmap_emblema(48, 48)
        self.assertFalse(pix.isNull())

    def test_panel_encabezado_estados(self) -> None:
        panel = PanelEncabezado()

        diag_disp = DiagnosticoOllama(
            EstadoServicioOllama.DISPONIBLE, "0.24.0", "0.4.1", Path("ollama.exe"), "http://127.0.0.1:11434", "Activo"
        )
        panel.actualizar_estado_ollama(diag_disp)
        self.assertIn("DISPONIBLE", panel.badge_estado.text())

        diag_det = DiagnosticoOllama(
            EstadoServicioOllama.DETENIDO, "0.24.0", None, Path("ollama.exe"), "http://127.0.0.1:11434", "Detenido"
        )
        panel.actualizar_estado_ollama(diag_det)
        self.assertIn("DETENIDO", panel.badge_estado.text())

    def test_panel_archivos_carga_y_seleccion_columnas(self) -> None:
        panel = PanelArchivos()
        ruta_csv = Path("pruebas/scratch_test.csv")
        ruta_csv.write_text("id,nombre,comentario\n1,Juan,Excelente servicio\n", encoding="utf-8")

        try:
            panel.cargar_archivo(ruta_csv)
            cols = panel.obtener_columnas_seleccionadas()
            self.assertEqual(cols, ["id", "nombre", "comentario"])

            # Probar boton de deseleccion total
            panel.btn_ninguna_cols.click()
            self.assertEqual(panel.obtener_columnas_seleccionadas(), [])

            # Probar boton de seleccion total
            panel.btn_todas_cols.click()
            self.assertEqual(panel.obtener_columnas_seleccionadas(), ["id", "nombre", "comentario"])
        finally:
            if ruta_csv.is_file():
                ruta_csv.unlink()

    def test_panel_configuracion_ia_modelos_y_prompts(self) -> None:
        panel = PanelConfiguracionIA()
        modelos = [InformacionModelo("qwen2.5:1.5b", 1024**3, "qwen2", "gguf", "1.5B", "Q4_K_M", "")]
        panel.actualizar_modelos(modelos)
        self.assertEqual(panel.modelo_seleccionado, "qwen2.5:1.5b")

        plantillas = [
            PlantillaPrompt("p1", "Clasificador", "Clasifica", "general", "Instruccion del sistema", columnas_salida=("clasificacion",)),
            PlantillaPrompt("p2", "Extractor", "Extrae", "extraccion", "Instruccion extractor", columnas_salida=("entidades",)),
        ]
        panel.actualizar_prompts(plantillas)
        self.assertEqual(panel.prompt_sistema_seleccionado, "Instruccion del sistema")
        self.assertEqual(panel.columnas_salida_modelo, ("clasificacion",))
        self.assertEqual(panel.tiempo_limite_lote_segundos, 60.0)

    def test_panel_configuracion_retiene_prompt_seleccionado_al_recargar(self) -> None:
        panel = PanelConfiguracionIA()
        plantillas = [
            PlantillaPrompt(identificador="p1", titulo="P1", descripcion="", categoria="c", contenido="c1"),
            PlantillaPrompt(identificador="p2", titulo="P2", descripcion="", categoria="c", contenido="c2"),
        ]
        panel.actualizar_prompts(plantillas)
        panel.combo_prompts.setCurrentIndex(1)
        self.assertEqual(panel.combo_prompts.currentData(), "p2")

        # Recargar el catalogo de plantillas: debe conservar 'p2'
        panel.actualizar_prompts(plantillas)
        self.assertEqual(panel.combo_prompts.currentData(), "p2")

    def test_cancelar_durante_ejecucion_llama_cancelar_del_coordinador(self) -> None:
        from procesos_ia.dominio.modelos import ConfiguracionTrabajo
        from procesos_ia.interfaz.hilos import HiloCoordinadorTrabajo

        mock_coord = MagicMock()
        config = ConfiguracionTrabajo(
            ruta_entrada=Path("entrada.csv"),
            directorio_salida=Path("salida/"),
            nombre_modelo="m",
            tamano_lote=1,
            limite_filas_particion=1000,
            ventana_contexto=2048,
            temperatura=0.1,
            tiempo_limite_lote_segundos=10.0,
            columnas_evaluar=("texto",),
            prompt_sistema="P",
            formato_salida="csv",
            columnas_salida_modelo=("clasificacion",),
        )

        hilo = HiloCoordinadorTrabajo(configuracion=config, coordinador=mock_coord)

        # Simular que se cancela durante el procesamiento de un lote
        def simular_lote():
            hilo.cancelar()
            return True

        mock_coord.procesar_siguiente_lote.side_effect = simular_lote

        hilo.run()
        mock_coord.cancelar.assert_called_once()
        mock_coord.cerrar.assert_called_once()

    def test_panel_telemetria_actualizacion(self) -> None:
        panel = PanelTelemetria()
        panel.actualizar_fase("[EN PROCESO]")
        self.assertIn("[EN PROCESO]", panel.label_fase.text())

        panel.actualizar_progreso(procesadas=50, totales=100, ram_mb=128.5, velocidad=12.0)
        self.assertEqual(panel.barra_progreso.value(), 50)
        self.assertIn("50 / 100", panel.val_filas.text())
        self.assertIn("128.5 MB", panel.val_ram.text())
        self.assertIn("12.0 filas/s", panel.val_velocidad.text())

        panel.agregar_log("[INFO] Prueba log")
        self.assertIn("Prueba log", panel.texto_bitacora.toPlainText())

    def test_panel_controles_transiciones(self) -> None:
        panel = PanelControles()
        self.assertTrue(panel.btn_iniciar.isEnabled())
        self.assertFalse(panel.btn_pausar.isEnabled())
        self.assertFalse(panel.btn_cancelar.isEnabled())

        panel.configurar_estado_ejecucion(en_ejecucion=True)
        self.assertFalse(panel.btn_iniciar.isEnabled())
        self.assertTrue(panel.btn_pausar.isEnabled())
        self.assertTrue(panel.btn_cancelar.isEnabled())

    def test_ventana_principal_inicializacion(self) -> None:
        mock_cliente = MagicMock(spec=ClienteHttpOllama)
        mock_cliente.verificar_estado.return_value = DiagnosticoOllama(
            estado=EstadoServicioOllama.DISPONIBLE,
            version_cliente="0.24.0",
            version_servidor="0.4.1",
            ruta_ejecutable=Path("ollama.exe"),
            url_base="http://127.0.0.1:11434",
            mensaje="Activo",
        )
        mock_cliente.listar_modelos.return_value = []

        mock_coordinador = MagicMock(spec=CoordinadorTrabajo)
        mock_prompts = MagicMock(spec=ServicioCatalogoPrompts)
        mock_prompts.listar_plantillas.return_value = []

        ventana = VentanaPrincipal(
            coordinador=mock_coordinador,
            cliente_ollama=mock_cliente,
            servicio_prompts=mock_prompts,
        )
        self.assertIsNotNone(ventana)
        self.assertEqual(ventana.windowTitle(), "PROCESOS_IA - Enriquecimiento Masivo de Datos")
        if ventana._hilo_modelos:
            ventana._hilo_modelos.wait(3000)
        mock_cliente.listar_modelos.assert_called_with(tiempo_limite=1.5, reintentos=0)

    def test_cache_modelos_ollama(self) -> None:
        ruta_temp = Path("pruebas/scratch_cache_test.json")
        try:
            cache = CacheModelosOllama(ruta_archivo=ruta_temp)
            self.assertEqual(cache.cargar(), [])

            modelos = [
                InformacionModelo(
                    nombre="llama3.2:1b",
                    tamano_bytes=1300000000,
                    familia="llama",
                    formato="gguf",
                    parametros="1B",
                    cuantizacion="Q4_K_M",
                    modificado_utc="2026-10-22",
                )
            ]
            self.assertTrue(cache.guardar(modelos))
            recuperados = cache.cargar()
            self.assertEqual(len(recuperados), 1)
            self.assertEqual(recuperados[0].nombre, "llama3.2:1b")
            self.assertEqual(recuperados[0].tamano_bytes, 1300000000)

            ruta_temp.write_text("invalid json", encoding="utf-8")
            self.assertEqual(cache.cargar(), [])
        finally:
            if ruta_temp.is_file():
                ruta_temp.unlink()

    def test_hilo_listar_modelos(self) -> None:
        mock_cliente = MagicMock(spec=ClienteHttpOllama)
        modelos_mock = [
            InformacionModelo(
                nombre="phi3:mini",
                tamano_bytes=2000000000,
                familia="phi3",
                formato="gguf",
                parametros="3.8B",
                cuantizacion="Q4_K_M",
                modificado_utc="",
            )
        ]
        mock_cliente.listar_modelos.return_value = modelos_mock

        hilo = HiloListarModelos(cliente_http=mock_cliente, tiempo_limite=2.0)
        recibidos = []
        hilo.senial_modelos.connect(recibidos.append)
        hilo.run()

        mock_cliente.listar_modelos.assert_called_once_with(tiempo_limite=1.5, reintentos=0)
        self.assertEqual(len(recibidos), 1)

    def test_hilo_listar_modelos_auto_inicia_si_detenido(self) -> None:
        from procesos_ia.dominio.excepciones import ErrorConexionRechazada

        mock_cliente = MagicMock(spec=ClienteHttpOllama)
        mock_cliente.es_ejecutable_disponible.return_value = True
        mock_cliente.iniciar_servicio.return_value = True

        mock_cliente.listar_modelos.side_effect = [
            ErrorConexionRechazada("Detenido"),
            [
                InformacionModelo(
                    nombre="qwen2.5:1.5b",
                    tamano_bytes=1000000000,
                    familia="qwen2",
                    formato="gguf",
                    parametros="1.5B",
                    cuantizacion="Q4_K_M",
                    modificado_utc="",
                )
            ],
        ]

        hilo = HiloListarModelos(cliente_http=mock_cliente, auto_iniciar=True, tiempo_limite=3.0)
        recibidos, mensajes = [], []
        hilo.senial_modelos.connect(recibidos.append)
        hilo.senial_mensaje.connect(mensajes.append)
        hilo.run()

        mock_cliente.iniciar_servicio.assert_called_once_with(
            tiempo_espera=6.0, cancelacion=hilo._cancelacion,
        )
        self.assertEqual(len(recibidos), 1)
        self.assertEqual(recibidos[0][0].nombre, "qwen2.5:1.5b")
        self.assertTrue(any("Levantando servidor" in m for m in mensajes))


if __name__ == "__main__":
    unittest.main()
