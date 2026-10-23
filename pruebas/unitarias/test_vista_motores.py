"""Pruebas unitarias para la vista de configuración de motores y selector de IA."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from procesos_ia.infraestructura.web.configuracion_web import ConfiguracionWeb
from procesos_ia.interfaz.app import crear_aplicacion
from procesos_ia.interfaz.componentes.panel_configuracion import PanelConfiguracionIA
from procesos_ia.interfaz.vista_motores import VistaConfiguracionMotores


class TestVistaConfiguracionMotores(unittest.TestCase):
    """Pruebas de la interfaz de configuración y alternancia de motores."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = crear_aplicacion([])

    def test_creacion_y_sincronizacion_inicial(self) -> None:
        cfg_web = ConfiguracionWeb(tiempo_espera_respuesta_segundos=60)
        vista = VistaConfiguracionMotores(motor_actual="deepseek", configuracion_web=cfg_web)

        self.assertTrue(vista.radio_deepseek.isChecked())
        self.assertFalse(vista.radio_gemini.isChecked())
        self.assertTrue(vista.grupo_web.isEnabled())
        self.assertEqual(vista.spin_espera.value(), 60)

    def test_alternar_entre_deepseek_y_gemini_web(self) -> None:
        vista = VistaConfiguracionMotores(motor_actual="deepseek")
        self.assertTrue(vista.radio_deepseek.isChecked())
        self.assertIn("DeepSeek", vista.banner.texto)

        vista.radio_gemini.setChecked(True)
        self.assertTrue(vista.radio_gemini.isChecked())
        self.assertIn("Gemini", vista.banner.texto)

    def test_aplicar_y_volver_emite_seniales(self) -> None:
        vista = VistaConfiguracionMotores(motor_actual="gemini")
        datos_recibidos = []

        vista.motor_configurado.connect(lambda motor, cfg: datos_recibidos.append((motor, cfg)))
        mock_volver = MagicMock()
        vista.volver_solicitado.connect(mock_volver)

        vista.btn_aplicar.click()

        self.assertEqual(len(datos_recibidos), 1)
        motor_sel, cfg_web = datos_recibidos[0]
        self.assertEqual(motor_sel, "gemini")
        self.assertIsInstance(cfg_web, ConfiguracionWeb)
        mock_volver.assert_called_once()

    def test_vista_motores_opciones_imagenes_y_modo(self) -> None:
        cfg = ConfiguracionWeb(modo_procesamiento="individual")
        vista = VistaConfiguracionMotores(motor_actual="deepseek", configuracion_web=cfg)
        self.assertEqual(vista.combo_modo.currentIndex(), 1)

        vista.input_imagenes.setText("C:/ruta/fotos")
        vista.combo_modo.setCurrentIndex(0)
        vista_cfg = vista._construir_configuracion_web()

        self.assertEqual(vista_cfg.modo_procesamiento, "lote")
        self.assertIsNotNone(vista_cfg.carpeta_imagenes)
        self.assertIn("fotos", str(vista_cfg.carpeta_imagenes))

    def test_componentes_operativos_en_vista_motores(self) -> None:
        vista = VistaConfiguracionMotores(motor_actual="gemini")
        self.assertTrue(hasattr(vista, "btn_ejecutar"))
        self.assertTrue(hasattr(vista, "btn_cancelar"))
        self.assertTrue(hasattr(vista, "btn_abrir_salida"))
        self.assertTrue(hasattr(vista, "panel_archivo"))
        self.assertTrue(hasattr(vista, "consola"))
        self.assertTrue(hasattr(vista, "combo_plantillas"))
        self.assertTrue(hasattr(vista, "txt_instrucciones"))
        self.assertTrue(hasattr(vista, "spin_lote"))

        # Validar seleccion de plantilla
        self.assertGreater(vista.combo_plantillas.count(), 1)
        vista.combo_plantillas.setCurrentIndex(1)
        self.assertIn(" | ", vista.txt_instrucciones.toPlainText())

    def test_servicio_procesamiento_web_instanciacion(self) -> None:
        from procesos_ia.aplicacion.servicio_procesamiento_web import ServicioProcesamientoWeb
        servicio = ServicioProcesamientoWeb()
        self.assertFalse(servicio._cancelado)
        servicio.cancelar()
        self.assertTrue(servicio._cancelado)


if __name__ == "__main__":
    unittest.main()
