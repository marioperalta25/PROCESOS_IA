"""Prueba explicita del ejecutable: dependencias, navegador y boton CSV con URL."""

import asyncio
import csv
import json
import os
import sys
from pathlib import Path
import tempfile

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.inicio.comprobacion_navegador import comprobar_navegador
from procesos_ia.dominio.ia_web.ficha_negocio import FichaNegocioLens
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.parametros_navegador import parametros_navegador


class SesionComprobacion:
    """Evita abrir Google Lens durante la comprobacion del boton y del hilo."""

    async def cerrar_navegador(self) -> None:
        return None


def comprobar_csv_url(raiz: Path, parametros: dict) -> dict:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from procesos_ia.interfaz.ia_web.vistas.vista_ia_general import VistaIAGeneral

    aplicacion = QApplication.instance() or QApplication([])
    original = raiz / parametros["nombre_csv"]
    with original.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerows([["id", "url"], ["1", parametros["fila_url"]]])
    configuracion = ConfiguracionWeb(directorio_base=raiz / "navegador_simulado")
    vista = VistaIAGeneral(
        gestor_sesion=SesionComprobacion(), configuracion_web=configuracion,
        enrutador=EnrutadorSalidas(raiz / "salidas"),
    )

    async def evaluar(**argumentos) -> FichaNegocioLens:
        return FichaNegocioLens(id_registro=argumentos["id_registro"], negocio="Comprobacion", estado_ia="EXITOSO")

    vista._servicio._procesador_archivo._ejecutor_lens = evaluar
    vista.combo_flujo.setCurrentIndex(vista.combo_flujo.findData("csv_lens"))
    vista.panel_archivo.cargar_archivo(original)
    vista.panel_archivo.combo_columna_img.setCurrentIndex(vista.panel_archivo.combo_columna_img.findText("url"))
    resultado = {}
    vista.btn_ejecutar.click()
    if vista._hilo is None:
        raise RuntimeError(f"CSV con URL no inicio: {vista.banner.texto}")
    vista._hilo.proceso_completado.connect(lambda mensaje, datos: resultado.update(completado=True))
    vista._hilo.proceso_fallido.connect(lambda error: resultado.update(error=error))
    vista._hilo.finished.connect(aplicacion.quit)
    limite = QTimer()
    limite.setSingleShot(True)
    limite.timeout.connect(aplicacion.quit)
    limite.start(parametros["tiempo_limite_segundos"] * 1000)
    aplicacion.exec()
    limite.stop()
    if vista._hilo.isRunning():
        vista._servicio.cancelar()
        vista._hilo.wait(parametros["tiempo_limite_segundos"] * 1000)
    salida = vista._servicio.ultima_salida
    if not resultado.get("completado") or not salida or not salida.is_file():
        raise RuntimeError(resultado.get("error", "CSV con URL no finalizo"))
    with salida.open(encoding="utf-8-sig", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    if len(filas) != 1 or filas[0].get("_estado_ia") != "EXITOSO":
        raise RuntimeError("La salida de CSV con URL no contiene el resultado esperado")
    vista.close()
    return {"boton_inicia": True, "hilo_finaliza": True, "filas_exportadas": len(filas), "motor_simulado": True}


def ejecutar_comprobacion(ruta_informe: Path) -> int:
    parametros = parametros_navegador()
    informe = {"version": parametros["version"]["aplicacion"], "correcto": False, "empaquetado": bool(getattr(sys, "frozen", False))}
    try:
        with tempfile.TemporaryDirectory(prefix="procesos_ia_comprobacion_", ignore_cleanup_errors=True) as temporal:
            raiz = Path(temporal)
            informe["csv_url"] = comprobar_csv_url(raiz, parametros["comprobacion"])
            informe["navegador"] = asyncio.run(comprobar_navegador(raiz / "chrome", parametros["comprobacion"]))
        informe["correcto"] = True
    except Exception as error:
        informe["error"] = f"{type(error).__name__}: {error}"
    ruta_informe.parent.mkdir(parents=True, exist_ok=True)
    ruta_informe.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if informe["correcto"] else 1
