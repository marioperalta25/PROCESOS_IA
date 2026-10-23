"""Presentación efímera de una respuesta en curso, aislada por conversación."""

from PySide6.QtCore import QObject, Slot


class ProgresoChat(QObject):
    def __init__(self, vista) -> None:
        super().__init__(vista)
        self.vista = vista
        self.identidad = None
        self.entrada = ""
        self.texto = ""
        self.reintentar = False

    def iniciar(self, identidad: str, entrada: str, reintentar: bool) -> None:
        self.identidad, self.entrada = identidad, entrada
        self.texto, self.reintentar = "", reintentar

    def finalizar(self) -> None:
        self.identidad = None
        self.texto = self.entrada = ""

    def mensajes(self, datos: dict) -> list[dict]:
        mensajes = datos["mensajes"]
        if datos["id"] != self.identidad:
            return mensajes
        mensajes = list(mensajes)
        pendiente_guardado = bool(mensajes and mensajes[-1]["rol"] == "user"
                                  and mensajes[-1]["estado"] == "pendiente"
                                  and mensajes[-1]["texto"] == self.entrada)
        if not self.reintentar and not pendiente_guardado:
            mensajes.append({"id": self.identidad + "-entrada", "rol": "user",
                             "texto": self.entrada, "estado": "en_curso"})
        elif mensajes:
            mensajes[-1] = {**mensajes[-1], "estado": "en_curso"}
        if self.texto:
            mensajes.append({"id": self.identidad + "-respuesta", "rol": "assistant",
                             "texto": self.texto, "estado": "generando"})
        return mensajes

    @Slot(str, str)
    def actualizar(self, identidad: str, texto: str) -> None:
        if identidad != self.identidad:
            return
        anterior, self.texto = self.texto, texto
        if identidad == self.vista._datos["id"]:
            if anterior:
                self.vista.transcripcion.actualizar_ultimo(texto)
            else:
                self.vista._pintar()
