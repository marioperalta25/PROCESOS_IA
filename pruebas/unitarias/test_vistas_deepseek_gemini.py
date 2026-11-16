"""Pruebas unitarias para las vistas desacopladas de DeepSeek Web y Gemini Web."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.interfaz.app import crear_aplicacion
from procesos_ia.interfaz.ia_web.vistas.vista_deepseek import VistaDeepSeek
from procesos_ia.interfaz.ia_web.vistas.vista_gemini import VistaGemini


class TestVistasDeepSeekGemini(unittest.TestCase):
    """Verifica componentes, seniales y configuracion en vistas independientes."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = crear_aplicacion([])

    def test_componentes_y_seniales_vista_deepseek(self) -> None:
        cfg = ConfiguracionWeb(tiempo_espera_respuesta_segundos=45)
        vista = VistaDeepSeek(configuracion_web=cfg)

        self.assertTrue(hasattr(vista, "combo_operacion"))
        self.assertTrue(hasattr(vista, "panel_imagenes_1a1"))
        self.assertEqual(vista.combo_operacion.count(), 2)
        self.assertEqual(vista.combo_operacion.itemData(0), "csv_texto")
        self.assertEqual(vista.combo_operacion.itemData(1), "extraccion_negocios_imagenes")
        self.assertTrue(hasattr(vista, "panel_archivo"))
        self.assertTrue(hasattr(vista, "combo_plantillas"))
        self.assertTrue(hasattr(vista, "txt_instrucciones"))
        self.assertTrue(hasattr(vista, "spin_lote"))
        self.assertTrue(hasattr(vista, "spin_rotacion"))
        self.assertTrue(hasattr(vista, "consola"))
        self.assertTrue(hasattr(vista, "btn_ejecutar"))
        self.assertTrue(hasattr(vista, "btn_cancelar"))
        self.assertTrue(hasattr(vista, "btn_abrir_salida"))
        self.assertTrue(hasattr(vista, "btn_iniciar_sesion"))
        self.assertTrue(hasattr(vista, "btn_ir_gemini"))
        self.assertTrue(hasattr(vista, "btn_ir_ia_general"))

        self.assertEqual(vista.spin_lote.value(), 5)
        self.assertEqual(vista.spin_rotacion.value(), 3)
        self.assertIn("DeepSeek", vista.banner.texto)

        # Probar senial de navegacion a Gemini
        senial_recibida = []
        vista.gemini_solicitado.connect(lambda: senial_recibida.append("gemini"))
        vista.btn_ir_gemini.click()
        self.assertIn("gemini", senial_recibida)

    def test_componentes_y_seniales_vista_gemini(self) -> None:
        cfg = ConfiguracionWeb(tiempo_espera_respuesta_segundos=45)
        vista = VistaGemini(configuracion_web=cfg)

        self.assertTrue(hasattr(vista, "combo_operacion"))
        self.assertTrue(hasattr(vista, "panel_imagenes_1a1"))
        self.assertEqual(vista.combo_operacion.count(), 2)
        self.assertEqual(vista.combo_operacion.itemData(0), "csv_texto")
        self.assertEqual(vista.combo_operacion.itemData(1), "extraccion_negocios_imagenes")
        self.assertTrue(hasattr(vista, "panel_archivo"))
        self.assertTrue(hasattr(vista, "combo_plantillas"))
        self.assertTrue(hasattr(vista, "txt_instrucciones"))
        self.assertTrue(hasattr(vista, "spin_lote"))
        self.assertTrue(hasattr(vista, "spin_rotacion"))
        self.assertTrue(hasattr(vista, "consola"))
        self.assertTrue(hasattr(vista, "btn_ejecutar"))
        self.assertTrue(hasattr(vista, "btn_cancelar"))
        self.assertTrue(hasattr(vista, "btn_abrir_salida"))
        self.assertTrue(hasattr(vista, "btn_iniciar_sesion"))
        self.assertTrue(hasattr(vista, "btn_ir_deepseek"))
        self.assertTrue(hasattr(vista, "btn_ir_ia_general"))

        self.assertEqual(vista.spin_lote.value(), 5)
        self.assertEqual(vista.spin_rotacion.value(), 2)
        self.assertIn("Gemini", vista.banner.texto)

        # Probar senial de navegacion a DeepSeek
        senial_recibida = []
        vista.deepseek_solicitado.connect(lambda: senial_recibida.append("deepseek"))
        vista.btn_ir_deepseek.click()
        self.assertIn("deepseek", senial_recibida)

    def test_limpiar_formularios_restablece_valores(self) -> None:
        vista_d = VistaDeepSeek()
        vista_d.txt_instrucciones.setPlainText("Prueba personalizada")
        vista_d.spin_lote.setValue(12)
        vista_d._limpiar_formulario()
        self.assertEqual(vista_d.txt_instrucciones.toPlainText(), "")
        self.assertEqual(vista_d.spin_lote.value(), 5)

        vista_g = VistaGemini()
        vista_g.txt_instrucciones.setPlainText("Prueba Gemini")
        vista_g.spin_rotacion.setValue(8)
        vista_g._limpiar_formulario()
        self.assertEqual(vista_g.txt_instrucciones.toPlainText(), "")
        self.assertEqual(vista_g.spin_rotacion.value(), 2)

    def test_cancelar_hilo_procesamiento_web_fuerza_cierre_inmediato(self) -> None:
        from unittest.mock import MagicMock
        from procesos_ia.interfaz.ia_web.hilos.hilo_procesamiento_web import HiloProcesamientoWeb

        servicio_mock = MagicMock()
        hilo = HiloProcesamientoWeb(servicio=servicio_mock, motor="gemini")
        hilo.cancelar()

        self.assertTrue(hilo._cancelado)
        servicio_mock.cancelar.assert_called_once()
        servicio_mock.forzar_cierre_inmediato.assert_called_once()

    def test_servicio_forzar_cierre_inmediato_limpia_bloqueos(self) -> None:
        from unittest.mock import MagicMock
        from procesos_ia.aplicacion.ia_web.motores.servicio_procesamiento_web import ServicioProcesamientoWeb

        config_mock = MagicMock()
        gestor_mock = MagicMock()
        gestor_mock._pid_navegador = 99999
        servicio = ServicioProcesamientoWeb(gestor_sesion=gestor_mock, configuracion_web=config_mock)

        servicio.forzar_cierre_inmediato()
        self.assertTrue(servicio._cancelado)
        config_mock.limpiar_bloqueos_perfil.assert_called_once()

    def test_hilo_lanzar_navegador_ejecuta_sin_name_error(self) -> None:
        from unittest.mock import patch, MagicMock
        from procesos_ia.interfaz.ia_web.hilos.hilo_navegador import HiloLanzarNavegador

        with patch("subprocess.Popen") as mock_popen, \
             patch("procesos_ia.infraestructura.web.base.lanzador_manual.aplicar_ventana_con_reintentos", return_value=True), \
             patch("nodriver.core.config.find_chrome_executable", return_value="C:/dummy/chrome.exe"), \
             patch("pathlib.Path.is_file", return_value=True):
            mock_proc = MagicMock(); mock_proc.pid = 1234
            mock_popen.return_value = mock_proc
            hilo = HiloLanzarNavegador("https://chat.deepseek.com")
            mensajes = []
            hilo.senial_exito.connect(mensajes.append)
            hilo.run()
            self.assertTrue(any("1234" in m for m in mensajes))


if __name__ == "__main__":
    unittest.main()
