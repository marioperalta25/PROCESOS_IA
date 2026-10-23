"""Cuota, durabilidad, contexto aislado y contrato HTTP del chat."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import MagicMock, patch

from procesos_ia.aplicacion.conversacion import ServicioConversacion
from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.infraestructura.ollama.chat import solicitar_chat
from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.ollama.parametros_chat import cargar_parametros_chat
from procesos_ia.infraestructura.persistencia.repositorio_chat import RepositorioChat


class PruebaChatLocal(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.parametros = cargar_parametros_chat()
        self.repo = RepositorioChat(Path(self.temporal.name), self.parametros)
        self.generar = MagicMock(return_value="Respuesta en español")
        self.servicio = ServicioConversacion(self.repo, self.generar, self.parametros)

    def responder(self, datos, entrada="Hola", cancelacion=None, reintentar=False):
        return self.servicio.responder(datos, entrada, "simulado", 4096, 0.1,
                                        cancelacion or Event(), reintentar)

    def test_persistencia_unicode_e_identidad_fuera_del_modelo(self):
        datos, _ = self.responder(self.repo.nuevo(), "¿Qué significa piñata?")
        self.assertEqual(self.repo.leer(datos["id"]), datos)
        self.assertEqual([m["estado"] for m in datos["mensajes"]], ["completo", "completo"])
        self.assertNotIn("id", self.generar.call_args.args[0][-1])
        self.assertEqual(self.repo.listar()[0]["titulo"], "¿Qué significa piñata?")

    def test_fallo_y_reintento_no_duplican_usuario(self):
        datos = self.repo.nuevo()
        self.generar.side_effect = ErrorProcesamiento("fallo simulado")
        with self.assertRaises(ErrorProcesamiento):
            self.responder(datos)
        pendiente = self.repo.leer(datos["id"])
        self.assertEqual(len(pendiente["mensajes"]), 1)
        identidad = pendiente["mensajes"][0]["id"]
        self.generar.side_effect = None
        completado, _ = self.responder(pendiente, reintentar=True)
        self.assertEqual(len(completado["mensajes"]), 2)
        self.assertEqual(completado["mensajes"][0]["id"], identidad)

    def test_cancelar_descarta_respuesta_sin_perder_usuario(self):
        cancelacion = Event()
        def generar(*args, **kwargs):
            cancelacion.set()
            return "No confirmar"
        self.generar.side_effect = generar
        datos, _ = self.responder(self.repo.nuevo(), cancelacion=cancelacion)
        self.assertEqual(len(datos["mensajes"]), 1)
        self.assertEqual(datos["mensajes"][0]["estado"], "cancelado")

    def test_contexto_no_incluye_otra_conversacion(self):
        anterior, _ = self.responder(self.repo.nuevo(), "SECRETO DE CHAT A")
        self.responder(self.repo.nuevo(), "CHAT B")
        contexto = self.generar.call_args.args[0]
        self.assertNotIn("SECRETO DE CHAT A", json.dumps(contexto))
        self.assertEqual(self.repo.leer(anterior["id"]), anterior)

    def test_contexto_acotado_conserva_turnos_completos(self):
        datos = self.repo.nuevo()
        for i in range(12):
            datos["mensajes"].extend([
                {"id": str(i), "rol": "user", "texto": "u" * 600, "estado": "completo"},
                {"id": str(i), "rol": "assistant", "texto": "a" * 600, "estado": "completo"},
            ])
        mensajes, reducido = self.servicio.preparar_contexto(datos, "último", 4096)
        self.assertTrue(reducido)
        self.assertLessEqual(self.servicio._coste(mensajes), self.servicio._presupuesto(4096))
        self.assertEqual([m["role"] for m in mensajes[1:-1]], ["user", "assistant"] * ((len(mensajes) - 2) // 2))

    def test_recorta_contexto_sin_generar_resumen_ni_perder_respuesta(self):
        datos = self.repo.nuevo()
        datos["modelo"] = "simulado"
        for i in range(8):
            datos["mensajes"].extend([
                {"id": str(i), "rol": "user", "texto": "u" * 500, "estado": "completo"},
                {"id": str(i), "rol": "assistant", "texto": "a" * 500, "estado": "completo"},
            ])
        def generar(*args, **kwargs):
            if kwargs.get("resumir"):
                raise ErrorProcesamiento("sin resumen")
            return "Respuesta válida"
        self.generar.side_effect = generar
        final, aviso = self.responder(datos)
        self.assertEqual(final["mensajes"][-1]["texto"], "Respuesta válida")
        self.assertEqual(aviso, self.parametros["textos"]["contexto_reducido"])
        self.generar.assert_called_once()
        self.assertEqual(final["resumen"], "")
        self.assertEqual(final["resumidos"], 0)

    def test_cuota_incluye_utf8_temporales_y_falla_antes_de_inferir(self):
        datos, _ = self.responder(self.repo.nuevo(), "áéíóú")
        original = self.repo._ruta(datos["id"]).read_bytes()
        self.parametros["limites"]["historial_bytes"] = self.repo.uso() + len(original) - 1
        with self.assertRaises(ErrorProcesamiento):
            self.repo.guardar(deepcopy(datos))
        self.assertEqual(self.repo._ruta(datos["id"]).read_bytes(), original)
        self.generar.reset_mock()
        with self.assertRaises(ErrorProcesamiento):
            self.responder(datos, "Otra pregunta")
        self.generar.assert_not_called()
        self.assertFalse(list(self.repo.directorio.glob("*.tmp")))

    def test_fallo_replace_preserva_confirmado_y_recupera_temporal(self):
        datos, _ = self.responder(self.repo.nuevo())
        original = self.repo._ruta(datos["id"]).read_bytes()
        with patch("os.replace", side_effect=OSError("disco simulado")):
            with self.assertRaises(OSError):
                self.repo.guardar(deepcopy(datos))
        self.assertEqual(self.repo._ruta(datos["id"]).read_bytes(), original)
        self.assertFalse(list(self.repo.directorio.glob("*.tmp")))

    def test_dos_instancias_excluyen_escrituras_y_borrado(self):
        otra = RepositorioChat(self.repo.directorio, self.parametros)
        with self.repo.operacion():
            with self.assertRaises(ErrorProcesamiento):
                otra.guardar(otra.nuevo())
            with self.assertRaises(ErrorProcesamiento):
                otra.borrar(otra.nuevo()["id"])

    def test_borrar_solo_seleccionado_y_rechazar_ruta_externa(self):
        a, _ = self.responder(self.repo.nuevo(), "A")
        b, _ = self.responder(self.repo.nuevo(), "B")
        self.repo.borrar(a["id"])
        self.assertFalse(self.repo.existe(a["id"]))
        self.assertEqual(self.repo.leer(b["id"]), b)
        with self.assertRaises(ErrorProcesamiento):
            self.repo.borrar("../fuera")

    def test_http_texto_sin_esquemas_sin_reintentos_y_lectura_acotada(self):
        cliente = ClienteHttpOllama()
        respuesta = MagicMock()
        respuesta.__enter__.return_value = respuesta
        respuesta.read.return_value = json.dumps({"message": {"content": "Hola"}, "done": True}).encode()
        with patch("urllib.request.urlopen", return_value=respuesta) as abrir:
            texto = solicitar_chat(cliente, [{"role": "user", "content": "Texto"}],
                                    "simulado", 4096, 0.1, self.parametros)
        self.assertEqual(texto, "Hola")
        cuerpo = json.loads(abrir.call_args.args[0].data)
        self.assertFalse(cuerpo["stream"])
        self.assertNotIn("format", cuerpo)
        self.assertNotIn("tools", cuerpo)
        respuesta.read.assert_called_once_with(self.parametros["limites"]["http_bytes"] + 1)

    def test_puerta_compartida_impide_inferencia_y_descarga_simultaneas(self):
        cliente = ClienteHttpOllama()
        cliente._puerta_inferencia.acquire()
        try:
            with patch("urllib.request.urlopen") as abrir:
                with self.assertRaises(ErrorProcesamiento):
                    cliente.generar_estructurado("simulado", "texto")
                self.assertFalse(cliente.liberar_memoria_modelo("simulado"))
                abrir.assert_not_called()
        finally:
            cliente._puerta_inferencia.release()

    def test_rechaza_respuesta_incompleta_o_excesiva(self):
        cliente = MagicMock()
        cliente.url_base = "http://ejemplo.invalid"
        for respuesta in ({"done": False, "message": {"content": "parcial"}},
                          {"done": True, "message": {"content": "x" * 32769}}):
            cliente._ejecutar_solicitud_json.return_value = respuesta
            with self.assertRaises(ErrorProcesamiento):
                solicitar_chat(cliente, [], "simulado", 4096, 0.1, self.parametros)

    def test_memoria_guardada_se_reutiliza_sin_otra_generacion(self):
        datos = self.repo.nuevo()
        datos["modelo"] = "simulado"
        datos["resumen"] = "Decisión revisada por el usuario"
        for i in range(5):
            datos["mensajes"].extend([
                {"id": str(i), "rol": "user", "texto": "u" * 500, "estado": "completo"},
                {"id": str(i), "rol": "assistant", "texto": "a" * 500, "estado": "completo"},
            ])
        final, _ = self.responder(datos)
        self.assertEqual(final["resumen"], datos["resumen"])
        self.assertEqual(final["resumidos"], 0)
        self.generar.assert_called_once()
        self.assertIn(datos["resumen"], self.generar.call_args.args[0][1]["content"])
        self.assertEqual(self.repo.leer(final["id"])["resumen"], datos["resumen"])

    def test_historial_borrado_no_resucita_y_version_obsoleta_no_sobrescribe(self):
        datos, _ = self.responder(self.repo.nuevo())
        obsoleto = deepcopy(datos)
        datos["titulo"] = "Nuevo título"
        self.repo.guardar(datos)
        with self.assertRaises(ErrorProcesamiento):
            self.repo.guardar(obsoleto, version_esperada=obsoleto["actualizado"])
        self.repo.borrar(datos["id"])
        self.generar.reset_mock()
        with self.assertRaises(ErrorProcesamiento):
            self.responder(datos)
        self.generar.assert_not_called()
        self.assertFalse(self.repo.existe(datos["id"]))

    def test_limite_http_evade_carga_completa_y_libera_puerta_tras_error(self):
        cliente = ClienteHttpOllama()
        respuesta = MagicMock()
        respuesta.__enter__.return_value = respuesta
        respuesta.read.return_value = b"x" * (self.parametros["limites"]["http_bytes"] + 1)
        with patch("urllib.request.urlopen", return_value=respuesta):
            with self.assertRaises(ErrorProcesamiento):
                solicitar_chat(cliente, [], "simulado", 4096, 0.1, self.parametros)
        self.assertFalse(cliente._puerta_inferencia.locked())
