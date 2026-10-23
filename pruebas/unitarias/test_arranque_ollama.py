"""Regresiones de arranque local, diagnostico y exclusividad sin procesos reales."""

import errno
import io
from pathlib import Path
from threading import Event
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from procesos_ia.dominio.excepciones import ErrorConexionRechazada, ErrorProcesamiento
from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.ollama.servicio_local import ServicioLocalOllama
from procesos_ia.interfaz.hilos import HiloListarModelos


class PruebaArranqueOllama(unittest.TestCase):
    def test_solo_conexion_rechazada_habilita_arranque(self) -> None:
        for error in (ErrorProcesamiento("HTTP 503"), ErrorProcesamiento("JSON invalido"),
                      TimeoutError("Demora"), PermissionError("Sin permiso")):
            with self.subTest(error=type(error).__name__):
                cliente = MagicMock(spec=ClienteHttpOllama)
                cliente.listar_modelos.side_effect = error
                hilo = HiloListarModelos(cliente, auto_iniciar=True)
                errores = []
                hilo.senial_error.connect(errores.append)
                hilo.run()
                cliente.iniciar_servicio.assert_not_called()
                self.assertEqual(errores, [str(error)])

    def test_consulta_al_arrancar_no_inicia_servicio(self) -> None:
        cliente = MagicMock(spec=ClienteHttpOllama)
        cliente.listar_modelos.side_effect = ErrorConexionRechazada("Rechazada")
        HiloListarModelos(cliente).run()
        cliente.iniciar_servicio.assert_not_called()

    def test_cliente_distingue_rechazo_de_permiso_y_timeout(self) -> None:
        cliente = ClienteHttpOllama()
        casos = (
            (ConnectionRefusedError(errno.ECONNREFUSED, "Rechazada"), ErrorConexionRechazada),
            (PermissionError(errno.EACCES, "Denegada"), ErrorProcesamiento),
            (TimeoutError("Agotado"), ErrorProcesamiento),
        )
        for causa, tipo in casos:
            with self.subTest(causa=causa), patch(
                "urllib.request.urlopen", side_effect=urllib.error.URLError(causa),
            ):
                with self.assertRaises(tipo) as resultado:
                    cliente.listar_modelos()
                self.assertIs(type(resultado.exception), tipo)

    def test_rechaza_destinos_remotos_antes_de_lanzar(self) -> None:
        for url in ("http://servidor.invalid:9999", "https://127.0.0.1:11434",
                    "http://usuario:clave@127.0.0.1:11434", "http://127.0.0.1:11434/api"):
            with self.subTest(url=url), patch("subprocess.Popen") as lanzar:
                servicio = ServicioLocalOllama(url)
                with self.assertRaises(ErrorProcesamiento):
                    servicio.iniciar(Path("ollama.exe"), MagicMock(), 1.0)
                lanzar.assert_not_called()

    def test_reutiliza_servidor_que_ya_responde(self) -> None:
        servicio = ServicioLocalOllama("http://127.0.0.1:11434")
        with patch("subprocess.Popen") as lanzar:
            self.assertTrue(servicio.iniciar(Path("ollama.exe"), MagicMock(return_value=[]), 1.0))
            lanzar.assert_not_called()

    def test_inyecta_puerto_y_conserva_diagnostico_de_salida(self) -> None:
        servicio = ServicioLocalOllama("http://127.0.0.1:12345")
        consultar = MagicMock(side_effect=ErrorConexionRechazada("Rechazada"))
        proceso = MagicMock()
        proceso.poll.return_value = 2
        proceso.stderr = io.BytesIO(b"fallo de inicio")
        with patch("subprocess.Popen", return_value=proceso) as lanzar:
            with self.assertRaisesRegex(ErrorProcesamiento, "codigo 2: fallo de inicio"):
                servicio.iniciar(Path("ollama.exe"), consultar, 1.0)
        self.assertEqual(lanzar.call_args.kwargs["env"]["OLLAMA_HOST"], "127.0.0.1:12345")
        self.assertFalse(lanzar.call_args.kwargs["shell"])

    def test_cancelacion_no_lanza_proceso(self) -> None:
        servicio = ServicioLocalOllama("http://127.0.0.1:11434")
        cancelacion = Event()
        cancelacion.set()
        with patch("subprocess.Popen") as lanzar:
            self.assertFalse(servicio.iniciar(Path("ollama.exe"), MagicMock(), 1.0, cancelacion))
            lanzar.assert_not_called()

    def test_cancelar_durante_consulta_impide_lanzamiento(self) -> None:
        servicio = ServicioLocalOllama("http://127.0.0.1:11434")
        cancelacion = Event()

        def consultar(**opciones):
            cancelacion.set()
            raise ErrorConexionRechazada("Rechazada")

        with patch("subprocess.Popen") as lanzar:
            self.assertFalse(servicio.iniciar(Path("ollama.exe"), consultar, 1.0, cancelacion))
            lanzar.assert_not_called()

    def test_impide_otro_arranque_concurrente(self) -> None:
        servicio = ServicioLocalOllama("http://127.0.0.1:11434")
        servicio._bloqueo.acquire()
        try:
            with patch("subprocess.Popen") as lanzar:
                with self.assertRaisesRegex(ErrorProcesamiento, "en curso"):
                    servicio.iniciar(Path("ollama.exe"), MagicMock(), 1.0)
                lanzar.assert_not_called()
        finally:
            servicio._bloqueo.release()

    def test_timeout_conserva_proceso_para_no_duplicar_arranque(self) -> None:
        servicio = ServicioLocalOllama("http://127.0.0.1:11434")
        proceso = MagicMock()
        proceso.poll.return_value = None
        proceso.stderr = io.BytesIO()
        consultar = MagicMock(side_effect=ErrorConexionRechazada("Rechazada"))
        with patch("subprocess.Popen", return_value=proceso) as lanzar, patch(
            "procesos_ia.infraestructura.ollama.servicio_local.time.monotonic",
            side_effect=[0.0, 0.0, 2.0, 0.0, 0.0, 2.0],
        ):
            for intento in range(2):
                with self.assertRaisesRegex(ErrorProcesamiento, "aun no responde"):
                    servicio.iniciar(Path("ollama.exe"), consultar, 1.0)
            lanzar.assert_called_once()
        proceso.terminate.assert_not_called()
        servicio._lectura.join()
