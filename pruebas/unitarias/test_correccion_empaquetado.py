"""Regresiones de geometria, configuracion y errores visibles antes de iniciar hilos."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.motores.servicio_procesamiento_web import ServicioProcesamientoWeb
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb, ConfiguracionVentanaWeb
from procesos_ia.infraestructura.web.base.controlador_ventana import aplicar_modo_flotante_sin_foco, buscar_manejador_ventana
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.infraestructura.web.base.lanzador_manual import lanzar_navegador_manual
from procesos_ia.interfaz.ia_web.hilos.hilo_navegador import HiloLanzarNavegador
from procesos_ia.interfaz.ia_web.vistas.vista_ia_general import VistaIAGeneral
from procesos_ia.interfaz.navegacion import NavegacionVistas


class PruebaCorreccionEmpaquetado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)
        self.ventana = ConfiguracionVentanaWeb(x=15, y=25, ancho=700, alto=420, siempre_al_frente=True)
        self.configuracion = ConfiguracionWeb(directorio_base=self.raiz, ventana=self.ventana)

    def test_lanzamiento_manual_usa_geometria_perfil_y_politica(self):
        chrome = self.raiz / "chrome.exe"
        chrome.touch()
        modulo = "procesos_ia.infraestructura.web.base.lanzador_manual."
        with patch("nodriver.core.config.find_chrome_executable", return_value=str(chrome)), \
             patch(modulo + "subprocess.Popen") as lanzar, \
             patch(modulo + "aplicar_ventana_con_reintentos", return_value=True) as aplicar:
            lanzar.return_value.pid = 1234
            self.assertEqual(lanzar_navegador_manual("about:blank", self.configuracion), 1234)
        argumentos = lanzar.call_args.args[0]
        self.assertIn("--window-size=700,420", argumentos)
        self.assertIn("--window-position=15,25", argumentos)
        self.assertIn(f"--user-data-dir={self.configuracion.directorio_perfil}", argumentos)
        self.assertEqual(aplicar.call_args.args[1:], (self.ventana, 1234, self.configuracion.directorio_perfil))

    def test_fallo_de_politica_manual_es_visible(self):
        with patch("procesos_ia.interfaz.ia_web.hilos.hilo_navegador.lanzar_navegador_manual", side_effect=RuntimeError("Politica no aplicada")):
            hilo = HiloLanzarNavegador("about:blank", self.configuracion)
            errores, exitos = [], []
            hilo.senial_error.connect(errores.append)
            hilo.senial_exito.connect(exitos.append)
            hilo.run()
        self.assertEqual(exitos, [])
        self.assertTrue(any("Politica no aplicada" in error for error in errores))

    def test_win32_aplica_tamano_topmost_y_no_roba_foco(self):
        import win32con
        modulo = "procesos_ia.infraestructura.web.base.controlador_ventana."
        with patch(modulo + "es_plataforma_compatible", return_value=True), \
             patch(modulo + "buscar_manejador_ventana", return_value=777), \
             patch(modulo + "win32gui.GetWindowLong", return_value=win32con.WS_EX_TOPMOST), \
             patch(modulo + "win32gui.SetWindowPos") as posicionar:
            self.assertTrue(aplicar_modo_flotante_sin_foco((), self.ventana, 1234, self.raiz))
        argumentos = posicionar.call_args.args
        self.assertEqual(argumentos[:6], (777, win32con.HWND_TOPMOST, 15, 25, 700, 420))
        self.assertTrue(argumentos[6] & win32con.SWP_NOACTIVATE)
        self.assertFalse(argumentos[6] & win32con.SWP_SHOWWINDOW)

    def test_chrome_reutilizado_se_identifica_por_perfil_sin_tocar_otro(self):
        modulo = "procesos_ia.infraestructura.web.base.controlador_ventana."

        def enumerar(evaluar, contexto):
            for hwnd in (10, 20):
                if evaluar(hwnd, contexto) is False:
                    break

        with patch(modulo + "es_plataforma_compatible", return_value=True), \
             patch(modulo + "obtener_pids_arbol", return_value={555}), \
             patch(modulo + "win32gui.EnumWindows", side_effect=enumerar), \
             patch(modulo + "win32gui.IsWindowVisible", return_value=True), \
             patch(modulo + "win32gui.GetWindowText", return_value="Chrome"), \
             patch(modulo + "win32process.GetWindowThreadProcessId", side_effect=[(0, 111), (0, 222)]), \
             patch(modulo + "_pertenece_al_perfil", side_effect=[False, True]):
            self.assertEqual(buscar_manejador_ventana(("Chrome",), 555, self.raiz), 20)

    def test_servicio_transmite_las_preferencias_al_gestor(self):
        gestor = GestorSesionNodriver(self.configuracion)
        servicio = ServicioProcesamientoWeb(gestor, self.configuracion, EnrutadorSalidas(self.raiz / "salidas"))
        nueva = replace(self.configuracion, ventana=replace(self.ventana, ancho=900))
        servicio.configurar(nueva)
        self.assertIs(gestor.configuracion, nueva)
        self.assertIs(servicio._config, nueva)

    def test_preferencias_llegan_a_las_vistas_ya_abiertas_sin_cambiar_perfiles(self):
        navegacion = NavegacionVistas.__new__(NavegacionVistas)
        navegacion.ventana = SimpleNamespace(_config_web=self.configuracion)
        vistas = []
        for nombre in ("general", "deepseek", "gemini"):
            configuracion = replace(self.configuracion, nombre_perfil=nombre)
            gestor = GestorSesionNodriver(configuracion)
            vistas.append(SimpleNamespace(_servicio=SimpleNamespace(gestor_sesion=gestor), _config_web=configuracion))
        navegacion.vista_ia_general, navegacion.vista_deepseek, navegacion.vista_gemini = vistas
        nueva = replace(self.configuracion, ventana=replace(self.ventana, ancho=950))
        navegacion.actualizar_configuracion_web(nueva)
        for vista, perfil in zip(vistas, ("general", "deepseek", "gemini")):
            self.assertEqual(vista._servicio.gestor_sesion.configuracion.ventana.ancho, 950)
            self.assertEqual(vista._servicio.gestor_sesion.configuracion.nombre_perfil, perfil)

    def test_error_al_preparar_csv_url_no_desaparece_en_una_aplicacion_sin_consola(self):
        vista = VistaIAGeneral(gestor_sesion=MagicMock(), enrutador=EnrutadorSalidas(self.raiz / "salidas"))
        self.addCleanup(vista.close)
        vista.combo_flujo.setCurrentIndex(vista.combo_flujo.findData("csv_lens"))
        original = self.raiz / "datos.csv"
        original.write_text("url\nhttps://ejemplo.invalid/a.png\n", encoding="utf-8")
        vista.panel_archivo.cargar_archivo(original)
        with patch("procesos_ia.aplicacion.ia_web.visual_1a1.procesador_archivo_urls.leer_filas_archivo_tabular", side_effect=TypeError("Fallo simulado de contrato")):
            vista.btn_ejecutar.click()
        self.assertIn("Fallo simulado de contrato", vista.banner.texto)
        self.assertIn("Fallo simulado de contrato", vista.consola.texto_log.toPlainText())
        self.assertTrue(vista.btn_ejecutar.isEnabled())
        self.assertIsNone(vista._hilo)

    def test_csv_lens_registra_en_consola_cuando_se_aborta_o_cancela_preparacion(self):
        vista = VistaIAGeneral(gestor_sesion=MagicMock(), enrutador=EnrutadorSalidas(self.raiz / "salidas"))
        self.addCleanup(vista.close)
        vista.combo_flujo.setCurrentIndex(vista.combo_flujo.findData("csv_lens"))
        vista.btn_ejecutar.click()
        self.assertIn("Seleccione un CSV", vista.consola.texto_log.toPlainText())
        original = self.raiz / "datos.csv"
        original.write_text("url\nhttps://ejemplo.invalid/a.png\n", encoding="utf-8")
        vista.panel_archivo.cargar_archivo(original)
        with patch("procesos_ia.interfaz.ia_web.vistas.vista_ia_general.preparar_trabajo_con_dialogo", return_value=None):
            vista.btn_ejecutar.click()
        self.assertIn("Preparación de CSV/Excel cancelada", vista.consola.texto_log.toPlainText())

    def test_win32_restaura_ventana_maximizada_sin_activar_foco(self):
        import win32con
        modulo = "procesos_ia.infraestructura.web.base.controlador_ventana."
        with patch(modulo + "es_plataforma_compatible", return_value=True), \
             patch(modulo + "buscar_manejador_ventana", return_value=777), \
             patch(modulo + "win32gui.IsIconic", return_value=False), \
             patch(modulo + "win32gui.GetWindowPlacement", return_value=(0, win32con.SW_SHOWMAXIMIZED, (0, 0), (0, 0), (0, 0, 100, 100))), \
             patch(modulo + "win32gui.ShowWindow") as mostrar, \
             patch(modulo + "win32gui.GetWindowLong", return_value=win32con.WS_EX_TOPMOST), \
             patch(modulo + "win32gui.SetWindowPos"):
            self.assertTrue(aplicar_modo_flotante_sin_foco((), self.ventana, 1234, self.raiz))
        mostrar.assert_called_once_with(777, win32con.SW_SHOWNOACTIVATE)

    def test_gestor_reaplica_ventana_si_cambia_configuracion_con_navegador_abierto(self):
        import asyncio
        gestor = GestorSesionNodriver(self.configuracion)
        gestor._navegador = MagicMock()
        gestor._ventana_aplicada = self.ventana
        nueva = replace(self.configuracion, ventana=replace(self.ventana, ancho=820))
        gestor.actualizar_configuracion(nueva)
        with patch("procesos_ia.infraestructura.web.base.gestor_sesion_nodriver.aplicar_ventana_con_reintentos", return_value=True) as aplicar:
            asyncio.run(gestor.iniciar_navegador())
        self.assertEqual(aplicar.call_args.args[1].ancho, 820)

    def test_preferencias_web_persisten_y_ancho_predeterminado_es_valido(self):
        from PySide6.QtCore import QSettings
        from procesos_ia.interfaz.comun.preferencias_web import cargar_configuracion_web, guardar_configuracion_web
        self.assertGreaterEqual(ConfiguracionVentanaWeb().ancho, 200)
        st = QSettings(str(self.raiz / "prefs.ini"), QSettings.Format.IniFormat)
        cfg = replace(self.configuracion, ventana=replace(self.ventana, ancho=640, alto=480, siempre_al_frente=False), tiempo_espera_respuesta_segundos=120)
        guardar_configuracion_web(cfg, st)
        cargada = cargar_configuracion_web(st)
        self.assertEqual((cargada.ventana.ancho, cargada.ventana.alto, cargada.ventana.siempre_al_frente), (640, 480, False))
        self.assertEqual(cargada.tiempo_espera_respuesta_segundos, 120)

    def test_win32_devuelve_foco_previo_solo_si_navegador_lo_robo(self):
        import win32con
        modulo = "procesos_ia.infraestructura.web.base.controlador_ventana."
        with patch(modulo + "es_plataforma_compatible", return_value=True), \
             patch(modulo + "buscar_manejador_ventana", return_value=777), \
             patch(modulo + "win32gui.GetWindowLong", return_value=win32con.WS_EX_TOPMOST), \
             patch(modulo + "win32gui.SetWindowPos"), \
             patch(modulo + "win32gui.GetForegroundWindow", return_value=777), \
             patch(modulo + "win32gui.IsWindow", return_value=True), \
             patch(modulo + "win32gui.SetForegroundWindow") as enfocar:
            self.assertTrue(aplicar_modo_flotante_sin_foco((), self.ventana, 1234, self.raiz, hwnd_foco_previo=999))
        enfocar.assert_called_once_with(999)

    def test_ultimo_aviso_ventana_se_propaga_a_callback_log(self):
        import asyncio
        from unittest.mock import AsyncMock
        from procesos_ia.aplicacion.ia_web.visual_1a1.servicio_ia_general import ServicioIAGeneral
        from procesos_ia.aplicacion.ia_web.motores.servicio_procesamiento_web import ServicioProcesamientoWeb

        gestor = MagicMock()
        gestor.ultimo_aviso_ventana = "Fallo Win32 simulado"
        gestor.abrir_nueva_pestana = AsyncMock(return_value=MagicMock())
        gestor.navegar_o_reutilizar = AsyncMock(return_value=MagicMock())
        logs_general, logs_motor = [], []
        s_gen = ServicioIAGeneral(gestor, self.configuracion, EnrutadorSalidas(self.raiz / "salidas"))
        s_gen._cancelado = True  # solo interesa probar la notificacion al abrir pestana
        with patch("procesos_ia.aplicacion.ia_web.visual_1a1.servicio_ia_general.abrir_modal_lens", AsyncMock(return_value=False)):
            s_gen._cancelado = False
            asyncio.run(s_gen.procesar_imagen_lens("https://ejemplo.invalid/a.png", callback_log=logs_general.append))
        self.assertTrue(any("Fallo Win32 simulado" in l for l in logs_general))
        s_web = ServicioProcesamientoWeb(gestor, self.configuracion, EnrutadorSalidas(self.raiz / "salidas"))
        asyncio.run(s_web._obtener_pestana("gemini", logs_motor.append))
        self.assertTrue(any("Fallo Win32 simulado" in l for l in logs_motor))

    def test_csv_lens_excluye_html_completo_del_csv_y_lo_conserva_en_md(self):
        import asyncio, csv
        from unittest.mock import AsyncMock
        from procesos_ia.aplicacion.ia_web.visual_1a1.procesador_archivo_urls import ProcesadorArchivoUrls
        from procesos_ia.dominio.ia_web.ficha_negocio import FichaNegocioLens

        entrada = self.raiz / "urls.csv"
        entrada.write_text("url\nhttps://ejemplo.invalid/1.png\n", encoding="utf-8")
        enrutador = EnrutadorSalidas(self.raiz / "salidas")
        ficha = FichaNegocioLens(
            id_registro="r1", negocio="Demo", estado_ia="EXITOSO", texto_sintesis="Sintesis breve",
            metadatos_adicionales={"html_completo": "<html>" + ("x" * 200_000) + "</html>"},
        )
        proc = ProcesadorArchivoUrls(AsyncMock(), enrutador, self.configuracion, AsyncMock(return_value=ficha))
        _, salida_csv = asyncio.run(proc.ejecutar(entrada, "url", generar_auditoria_md=True))
        with salida_csv.open(encoding="utf-8-sig", newline="") as f:
            filas = list(csv.DictReader(f))
        self.assertNotIn("metadatos_adicionales", filas[0])
        self.assertNotIn("enlaces", filas[0])
        self.assertIn("Desplegar HTML completo", salida_csv.with_suffix(".md").read_text(encoding="utf-8"))

    def test_taskkill_oculta_ventana_consola_en_windows(self):
        import subprocess
        from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import terminar_arbol_procesos
        with patch("procesos_ia.infraestructura.web.base.gestor_sesion_nodriver.os.name", "nt"), \
             patch("procesos_ia.infraestructura.web.base.gestor_sesion_nodriver.subprocess.run") as ejecutar:
            terminar_arbol_procesos(999999)
        self.assertEqual(ejecutar.call_args.kwargs.get("creationflags"), getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def test_modo_ia_urls_hibrido_visibilidad_y_construccion_instrucciones(self):
        from procesos_ia.aplicacion.ia_web.conversacional.procesador_urls_modo_ia import construir_instrucciones_urls_modo_ia
        vista = VistaIAGeneral(gestor_sesion=MagicMock(), enrutador=EnrutadorSalidas(self.raiz / "salidas"))
        self.addCleanup(vista.close)
        idx = vista.combo_flujo.findData("modo_ia_urls")
        self.assertGreaterEqual(idx, 0)
        vista.combo_flujo.setCurrentIndex(idx)
        self.assertFalse(vista.panel_archivo.isHidden())
        self.assertFalse(vista.panel_modo_ia_urls.isHidden())
        self.assertTrue(vista.panel_modo_chat.isHidden())
        params = vista.panel_modo_ia_urls.obtener_parametros()
        inst = construir_instrucciones_urls_modo_ia(params["campos_activos"], "Solo locales")
        self.assertIn("Solo locales", inst)
        self.assertIn("negocio", inst)

    def test_estado_tabular_se_aisla_y_limpia_tras_cinco_dias(self):
        import os, time
        from procesos_ia.aplicacion.comun.identidad_tabular import IdentidadTabular
        from procesos_ia.aplicacion.comun.trabajo_tabular import TrabajoTabular, limpiar_estados_antiguos
        filas = [{"url": "https://ejemplo.invalid/1.png"}]
        enr = EnrutadorSalidas(self.raiz / "salidas")
        trabajo = TrabajoTabular(filas, IdentidadTabular.crear(None, "modo_ia", filas, "inst", ["url"]))
        with trabajo.abrir(enr, "salida_final.csv"):
            ruta_final = trabajo.finalizar("completados")
        dir_estado = ruta_final.parent / ".estado"
        self.assertTrue(dir_estado.is_dir())
        antiguo = time.time() - (6 * 86400)
        for arch in dir_estado.iterdir():
            os.utime(arch, (antiguo, antiguo))
        eliminados = limpiar_estados_antiguos(enr.gestor_procesos(), "modo_ia", trabajo.parametros)
        self.assertEqual(eliminados, 1)
        self.assertFalse(dir_estado.exists())
        self.assertTrue(ruta_final.is_file())
