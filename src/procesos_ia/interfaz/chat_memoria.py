"""Acción explícita de recordar texto mediante la memoria existente del chat."""

from PySide6.QtCore import QObject, Slot
from procesos_ia.dominio.excepciones import ErrorProcesamiento


class MemoriaChat(QObject):
    def __init__(self, vista) -> None:
        super().__init__(vista)
        self.vista = vista
        vista.transcripcion.recordar_solicitado.connect(self.recordar)

    @Slot(str, str)
    def recordar(self, identidad: str, texto: str) -> None:
        vista = self.vista
        if vista._hilo is not None:
            return
        mensaje = next((m for m in vista._datos["mensajes"] if m["id"] == identidad
                        and m["estado"] == "completo"), None)
        texto = texto.strip()
        if mensaje is None or not texto or texto not in mensaje["texto"]:
            return
        textos = vista.parametros["textos"]
        clave = "recuerdo_usuario" if mensaje["rol"] == "user" else "recuerdo_asistente"
        recuerdo = textos[clave].format(texto=texto)
        memoria = vista._datos["resumen"].strip()
        if recuerdo in memoria:
            vista.banner.mostrar_info(textos["recuerdo_existente"])
            return
        candidato = textos["separador_recuerdos"].join(p for p in (memoria, recuerdo) if p)
        try:
            vista.servicio.validar_memoria(candidato)
        except ErrorProcesamiento:
            vista._editar_memoria()
            vista.resumen.setPlainText(candidato)
            vista.banner.mostrar_alerta(textos["recuerdo_extenso"])
            return
        try:
            vista._datos = vista.servicio.guardar_memoria(vista._datos, candidato)
            vista._refrescar_lista()
            vista._pintar()
            vista.banner.mostrar_info(textos["recuerdo_guardado"])
        except (OSError, ErrorProcesamiento) as error:
            vista.banner.mostrar_error(str(error))
