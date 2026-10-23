"""Pruebas unitarias para el protector antirebote de botones y notificación de acciones."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QPushButton

from procesos_ia.interfaz.protector_botones import (
    ProtectorBotones,
    conectar_boton_protegido,
    establecer_notificador_predeterminado,
    obtener_notificador_predeterminado,
)


class PruebaProtectorBotones(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        establecer_notificador_predeterminado(None)

    def test_evita_pulsaciones_multiples_en_enfriamiento(self) -> None:
        boton = QPushButton("Acción")
        contador = 0

        def accion() -> None:
            nonlocal contador
            contador += 1

        conectar_boton_protegido(boton, accion, "[INFO] Ejecutando acción...", tiempo_bloqueo_ms=100)

        # Primer clic: debe ejecutarse y deshabilitar el botón
        boton.click()
        self.assertEqual(contador, 1)
        self.assertFalse(boton.isEnabled())

        # Segundo clic inmediato mientras está en enfriamiento: no debe ejecutarse
        boton.click()
        self.assertEqual(contador, 1)

    def test_notificacion_local_al_pulsar(self) -> None:
        boton = QPushButton("Guardar")
        mensajes_recibidos: list[str] = []

        def notificador(mensaje: str) -> None:
            mensajes_recibidos.append(mensaje)

        conectar_boton_protegido(
            boton,
            lambda: None,
            mensaje_notificacion="[INFO] Guardando...",
            notificador=notificador,
            tiempo_bloqueo_ms=50,
        )

        boton.click()
        self.assertEqual(mensajes_recibidos, ["[INFO] Guardando..."])

    def test_notificacion_predeterminada_global(self) -> None:
        boton = QPushButton("Abrir")
        mensajes_recibidos: list[str] = []
        establecer_notificador_predeterminado(mensajes_recibidos.append)

        conectar_boton_protegido(
            boton,
            lambda: None,
            mensaje_notificacion="[INFO] Abriendo...",
            tiempo_bloqueo_ms=50,
        )

        boton.click()
        self.assertEqual(mensajes_recibidos, ["[INFO] Abriendo..."])

    def test_restablece_habilitacion_tras_tiempo(self) -> None:
        boton = QPushButton("Procesar")
        conectar_boton_protegido(boton, lambda: None, tiempo_bloqueo_ms=10)

        boton.click()
        self.assertFalse(boton.isEnabled())

        # Procesar eventos de Qt hasta que se complete el temporizador
        for _ in range(5):
            QCoreApplication.processEvents()
            self.app.processEvents()

    def test_instancia_reutilizada_en_mismo_boton(self) -> None:
        boton = QPushButton("Boton")
        conectar_boton_protegido(boton, lambda: None)
        instancia_1 = getattr(boton, "_protector_instancia", None)
        self.assertIsNotNone(instancia_1)


if __name__ == "__main__":
    unittest.main()
