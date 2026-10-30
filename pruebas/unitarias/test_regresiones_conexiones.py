"""Regresiones de anotaciones, seniales y recuperacion desde la entrada real de interfaz."""

import csv
from dataclasses import replace
from pathlib import Path
import tempfile
from typing import get_type_hints
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.reanudacion_local import buscar_continuacion_local
from procesos_ia.aplicacion.ia_web.visual_1a1.procesador_url_individual import ProcesadorUrlIndividual
from procesos_ia.dominio.modelos import ConfiguracionTrabajo
from procesos_ia.interfaz.composicion_trabajo import iniciar_trabajo_local
from procesos_ia.interfaz.hilos import HiloCoordinadorTrabajo
from procesos_ia.interfaz.ia_web.vistas.vista_motores import VistaConfiguracionMotores


class PruebaRegresionesConexiones(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)
        self.enrutador = EnrutadorSalidas(self.raiz)

    def _interrumpir(self, copia: bool = False, legado: bool = False):
        entrada = self.raiz / "clientes.csv"
        entrada.write_text("texto\nPrimera entrada\nSegunda entrada\n", encoding="utf-8")
        salida = None
        if legado:
            directorio = self.raiz / "analisis" / "clientes_20261030"
        else:
            if copia:
                self.enrutador.reservar_salida("ia_local", "resultado_procesado.csv", entrada.stem)
            salida = self.enrutador.reservar_salida("ia_local", "resultado_procesado.csv", entrada.stem)
            directorio = salida.directorio
        configuracion = ConfiguracionTrabajo(
            entrada, directorio, "simulado", 1, 1000, 512, 0.0, 10.0,
            ("texto",), "Evaluar", "csv", ("calificacion",),
        )
        inferencia = MagicMock()
        inferencia.procesar_lote.side_effect = [
            [{"identificador": "clientes.csv:1", "calificacion": "A"}], RuntimeError("Corte simulado"),
        ]
        hilo = HiloCoordinadorTrabajo(configuracion, servicio_inferencia=inferencia, salida=salida)
        errores = []
        hilo.senial_error.connect(errores.append)
        hilo.run()
        self.assertEqual(len(errores), 1)
        if salida:
            configuracion = replace(configuracion, directorio_salida=salida.directorio)
        return configuracion, salida

    def _componer(self, configuracion, decision: str):
        ventana = MagicMock()
        ventana._enrutador = self.enrutador
        ventana.panel_archivos.raiz_salidas = self.raiz
        modulo = "procesos_ia.interfaz.composicion_trabajo."
        with patch(modulo + "elegir_continuacion_local", return_value=decision) as eleccion:
            with patch(modulo + "HiloCoordinadorTrabajo") as constructor:
                iniciar_trabajo_local(ventana, configuracion)
                argumentos = constructor.call_args.kwargs if constructor.called else None
        return ventana, argumentos, eleccion

    def test_las_anotaciones_publicas_del_ejecutor_url_se_resuelven(self) -> None:
        anotaciones = get_type_hints(ProcesadorUrlIndividual.__init__)
        self.assertIn("ejecutor_lens", anotaciones)
        self.assertIn("return", get_type_hints(ProcesadorUrlIndividual.ejecutar))

    def test_botones_trasladados_conservan_sus_conexiones(self) -> None:
        with patch.object(VistaConfiguracionMotores, "_ejecutar_procesamiento_web") as ejecutar:
            with patch.object(VistaConfiguracionMotores, "_cancelar_procesamiento") as cancelar:
                vista = VistaConfiguracionMotores(enrutador=self.enrutador)
                general, plantillas = [], []
                vista.ia_general_solicitado.connect(lambda: general.append(True))
                vista.plantillas_web_solicitadas.connect(lambda: plantillas.append(True))
                vista.btn_ejecutar.click()
                vista.btn_cancelar.setEnabled(True)
                vista.btn_cancelar.click()
                vista.btn_ia_general.click()
                vista.btn_plantillas_ia_web.click()
                ejecutar.assert_called_once()
                cancelar.assert_called_once()
                self.assertEqual(general, [True])
                self.assertEqual(plantillas, [True])
                vista.combo_operacion.setCurrentIndex(vista.combo_operacion.findData("carpeta_imagenes"))
                self.assertFalse(vista.spin_lote.isEnabled())
                self.assertFalse(vista.grupo_directo.isHidden())
                vista.close()

    def test_interfaz_reanuda_solo_la_fila_no_confirmada(self) -> None:
        configuracion, _ = self._interrumpir()
        _, argumentos, eleccion = self._componer(configuracion, "continuar")
        eleccion.assert_called_once()
        inferencia = MagicMock()
        inferencia.procesar_lote.side_effect = lambda lote, cfg: [
            {"identificador": fila.identificador, "calificacion": "B"} for fila in lote
        ]
        hilo = HiloCoordinadorTrabajo(
            argumentos["configuracion"], servicio_inferencia=inferencia, salida=argumentos["salida"],
        )
        errores = []
        hilo.senial_error.connect(errores.append)
        hilo.run()
        self.assertEqual(errores, [])
        enviados = [f.identificador for llamada in inferencia.procesar_lote.call_args_list for f in llamada.args[0]]
        self.assertEqual(enviados, ["clientes.csv:2"])
        with argumentos["salida"].ruta.open(encoding="utf-8-sig", newline="") as archivo:
            filas = list(csv.DictReader(archivo))
        self.assertEqual([fila["calificacion"] for fila in filas], ["A", "B"])

    def test_continuacion_conserva_nombre_copia_y_avance(self) -> None:
        configuracion, salida = self._interrumpir(copia=True)
        self.assertEqual(salida.nombre_archivo, "resultado_procesado_copia1.csv")
        _, argumentos, _ = self._componer(configuracion, "continuar")
        self.assertEqual(argumentos["salida"].nombre_archivo, salida.nombre_archivo)
        hilo = HiloCoordinadorTrabajo(
            argumentos["configuracion"], servicio_inferencia=MagicMock(), salida=argumentos["salida"],
        )
        try:
            self.assertEqual(hilo._coordinador.iniciar_o_reanudar(), 1)
        finally:
            hilo._coordinador.cerrar()

    def test_continuacion_anterior_conserva_su_carpeta(self) -> None:
        configuracion, _ = self._interrumpir(legado=True)
        _, argumentos, _ = self._componer(configuracion, "continuar")
        self.assertIsNone(argumentos["salida"])
        self.assertEqual(argumentos["configuracion"].directorio_salida, configuracion.directorio_salida)
        hilo = HiloCoordinadorTrabajo(argumentos["configuracion"], servicio_inferencia=MagicMock())
        try:
            self.assertEqual(hilo._coordinador.iniciar_o_reanudar(), 1)
        finally:
            hilo._coordinador.cerrar()

    def test_origen_modificado_con_igual_nombre_crea_copia(self) -> None:
        configuracion, salida = self._interrumpir()
        contenido = salida.ruta.read_bytes()
        configuracion.ruta_entrada.write_text("texto\nContenido nuevo\n", encoding="utf-8")
        _, argumentos, eleccion = self._componer(configuracion, "continuar")
        eleccion.assert_not_called()
        self.assertNotEqual(argumentos["salida"].directorio, salida.directorio)
        self.assertEqual(argumentos["salida"].nombre_archivo, "resultado_procesado_copia1.csv")
        self.assertEqual(salida.ruta.read_bytes(), contenido)

    def test_cambio_de_evaluacion_no_reutiliza_resultados(self) -> None:
        configuracion, _ = self._interrumpir()
        modificada = replace(configuracion, prompt_sistema="Otro criterio")
        self.assertIsNone(buscar_continuacion_local(modificada, self.enrutador, self.raiz))

    def test_elegir_nuevo_no_modifica_el_respaldo_anterior(self) -> None:
        configuracion, salida = self._interrumpir()
        contenido = salida.ruta.read_bytes()
        _, argumentos, _ = self._componer(configuracion, "nuevo")
        self.assertEqual(argumentos["salida"].nombre_archivo, "resultado_procesado_copia1.csv")
        self.assertEqual(salida.ruta.read_bytes(), contenido)

    def test_cancelar_eleccion_no_inicia_ni_mueve_archivos(self) -> None:
        configuracion, salida = self._interrumpir()
        ventana, argumentos, _ = self._componer(configuracion, "cancelar")
        self.assertIsNone(argumentos)
        ventana.panel_controles.configurar_estado_ejecucion.assert_not_called()
        self.assertTrue(salida.ruta.exists())
