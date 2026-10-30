"""Eleccion de continuacion local sin trasladar decisiones al escritor compartido."""

from PySide6.QtWidgets import QMessageBox, QWidget

from procesos_ia.aplicacion.reanudacion_local import ContinuacionLocal
from procesos_ia.infraestructura.prompts.parametros import cargar_parametros_evaluacion


def elegir_continuacion_local(parent: QWidget, continuacion: ContinuacionLocal) -> str:
    textos = cargar_parametros_evaluacion()
    cuadro = QMessageBox(parent)
    cuadro.setWindowTitle(textos["titulo_continuacion"])
    cuadro.setText(textos["mensaje_continuacion"].format(
        confirmados=continuacion.confirmados, directorio=continuacion.directorio,
    ))
    continuar = cuadro.addButton(textos["continuar_trabajo"], QMessageBox.ButtonRole.AcceptRole)
    nuevo = cuadro.addButton(textos["nuevo_trabajo"], QMessageBox.ButtonRole.ActionRole)
    cuadro.addButton(textos["cancelar_continuacion"], QMessageBox.ButtonRole.RejectRole)
    cuadro.setDefaultButton(continuar)
    cuadro.exec()
    if cuadro.clickedButton() == continuar:
        return "continuar"
    if cuadro.clickedButton() == nuevo:
        return "nuevo"
    return "cancelar"
