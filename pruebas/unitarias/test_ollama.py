"""Pruebas unitarias para el cliente HTTP de Ollama y el servicio de inferencia."""

from __future__ import annotations

import io
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.dominio.modelos import ConfiguracionTrabajo, RegistroEntrada
from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.ollama.modelos import EstadoServicioOllama
from procesos_ia.infraestructura.ollama.servicio_inferencia import (
    ServicioInferenciaOllama,
)


class PruebaOllama(unittest.TestCase):
    def test_verificar_estado_disponible(self) -> None:
        cliente = ClienteHttpOllama(url_base="http://127.0.0.1:11434")

        mock_respuesta = MagicMock()
        mock_respuesta.status = 200
        mock_respuesta.read.return_value = json.dumps({"version": "0.4.1"}).encode("utf-8")
        mock_respuesta.__enter__.return_value = mock_respuesta

        with patch("urllib.request.urlopen", return_value=mock_respuesta):
            diagnostico = cliente.verificar_estado()
            self.assertEqual(diagnostico.estado, EstadoServicioOllama.DISPONIBLE)
            self.assertEqual(diagnostico.version_servidor, "0.4.1")

    def test_verificar_estado_detenido_cuando_hay_ejecutable(self) -> None:
        cliente = ClienteHttpOllama(url_base="http://127.0.0.1:11434")

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Conexion rechazada")):
            with patch("shutil.which", return_value="C:/Program Files/Ollama/ollama.exe"):
                diagnostico = cliente.verificar_estado()
                self.assertEqual(diagnostico.estado, EstadoServicioOllama.DETENIDO)
                self.assertIn("detenido", diagnostico.mensaje)

    def test_listar_modelos(self) -> None:
        cliente = ClienteHttpOllama()
        respuesta_falsa = {
            "models": [
                {
                    "name": "qwen2.5:1.5b",
                    "size": 986000000,
                    "details": {
                        "family": "qwen2",
                        "format": "gguf",
                        "parameter_size": "1.5B",
                        "quantization_level": "Q4_K_M",
                    },
                    "modified_at": "2026-10-22T08:00:00Z",
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(respuesta_falsa).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            modelos = cliente.listar_modelos()
            self.assertEqual(len(modelos), 1)
            self.assertEqual(modelos[0].nombre, "qwen2.5:1.5b")
            self.assertEqual(modelos[0].parametros, "1.5B")

    def test_servicio_inferencia_asegura_identificador(self) -> None:
        cliente_mock = MagicMock(spec=ClienteHttpOllama)
        cliente_mock.generar_estructurado.return_value = {
            "clasificacion": "urgente",
            "categoria": "soporte",
        }

        servicio = ServicioInferenciaOllama(cliente_http=cliente_mock)

        config = ConfiguracionTrabajo(
            ruta_entrada=Path("entrada.csv"),
            directorio_salida=Path("salida/"),
            nombre_modelo="qwen2.5:1.5b",
            tamano_lote=2,
            limite_filas_particion=1_000_000,
            ventana_contexto=2048,
            temperatura=0.1,
            tiempo_limite_lote_segundos=15.0,
            columnas_evaluar=("mensaje",),
            prompt_sistema="Clasifica el mensaje.",
            formato_salida="csv",
            columnas_salida_modelo=("clasificacion", "categoria"),
        )

        lote = [
            RegistroEntrada("doc1:1", 1, {"mensaje": "Ayuda"}, {"mensaje": "Ayuda"}),
            RegistroEntrada("doc1:2", 2, {"mensaje": "Factura"}, {"mensaje": "Factura"}),
        ]

        respuestas = servicio.procesar_lote(lote, config)
        self.assertEqual(len(respuestas), 2)
        self.assertEqual(respuestas[0]["identificador"], "doc1:1")
        self.assertEqual(respuestas[1]["identificador"], "doc1:2")
        self.assertEqual(respuestas[0]["clasificacion"], "urgente")

    def test_servicio_inferencia_rechaza_columnas_no_coincidentes(self) -> None:
        cliente_mock = MagicMock(spec=ClienteHttpOllama)
        servicio = ServicioInferenciaOllama(cliente_http=cliente_mock)

        config = ConfiguracionTrabajo(
            ruta_entrada=Path("entrada.csv"),
            directorio_salida=Path("salida/"),
            nombre_modelo="qwen2.5:1.5b",
            tamano_lote=1,
            limite_filas_particion=1_000_000,
            ventana_contexto=2048,
            temperatura=0.1,
            tiempo_limite_lote_segundos=15.0,
            columnas_evaluar=("columna_inexistente",),
            prompt_sistema="Clasifica.",
            formato_salida="csv",
            columnas_salida_modelo=("clasificacion",),
        )

        lote = [
            RegistroEntrada("doc1:1", 1, {"secreto": "no_enviar"}, {"secreto": "no_enviar"}),
        ]

        respuestas = servicio.procesar_lote(lote, config)
        self.assertEqual(len(respuestas), 1)
        self.assertIn("error_configuracion", respuestas[0])
        self.assertIn("Faltan columnas", respuestas[0]["error_configuracion"])
        cliente_mock.generar_estructurado.assert_not_called()

    def test_verificar_estado_error_conexion_en_http_503(self) -> None:
        cliente = ClienteHttpOllama(url_base="http://127.0.0.1:11434")
        error_503 = urllib.error.HTTPError(
            url="http://127.0.0.1:11434/api/version",
            code=503,
            msg="Service Unavailable",
            hdrs={},  # type: ignore
            fp=None,
        )

        with patch("urllib.request.urlopen", side_effect=error_503):
            with patch("shutil.which", return_value="C:/Program Files/Ollama/ollama.exe"):
                diagnostico = cliente.verificar_estado()
                self.assertEqual(diagnostico.estado, EstadoServicioOllama.ERROR_CONEXION)
                self.assertIn("HTTP 503", diagnostico.mensaje)

    def test_generar_estructurado_falla_rapido_en_http_404_sin_reintentos(self) -> None:
        cliente = ClienteHttpOllama(reintentos_maximos=2)
        error_fp = io.BytesIO(b'{"error": "model \'inexistente\' not found"}')
        error_404 = urllib.error.HTTPError(
            url="http://127.0.0.1:11434/api/generate",
            code=404,
            msg="Not Found",
            hdrs={},  # type: ignore
            fp=error_fp,
        )

        with patch("urllib.request.urlopen", side_effect=error_404) as mock_urlopen:
            with self.assertRaises(ErrorProcesamiento) as contexto:
                cliente.generar_estructurado(
                    modelo="inexistente",
                    prompt="test",
                )
            self.assertEqual(mock_urlopen.call_count, 1)
            self.assertIn("Error HTTP 404", str(contexto.exception))
            self.assertIn("model 'inexistente' not found", str(contexto.exception))

    def test_generar_estructurado_convierte_json_invalido_en_error_procesamiento(self) -> None:
        cliente = ClienteHttpOllama()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html>502 Bad Gateway</html>"
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(ErrorProcesamiento) as contexto:
                cliente.generar_estructurado(modelo="qwen2.5:1.5b", prompt="test")
            self.assertIn("no es un JSON valido", str(contexto.exception))


if __name__ == "__main__":
    unittest.main()
