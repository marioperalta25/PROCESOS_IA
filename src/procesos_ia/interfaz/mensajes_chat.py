"""Burbujas nativas, seleccionables y acotadas para mensajes de texto plano."""

from math import ceil
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QFontMetricsF, QTextCursor, QTextOption
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)


class TextoMensaje(QTextEdit):
    def __init__(self, texto: str, extra_alto: int, parent=None) -> None:
        super().__init__(parent)
        self._extra_alto = extra_alto
        self.setFixedHeight(extra_alto)
        self.setObjectName("texto_mensaje")
        self.setReadOnly(True)
        self.setAcceptRichText(False)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(0)
        self.setPlainText(texto)
        self.document().documentLayout().documentSizeChanged.connect(self._ajustar_alto)

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        self.document().setTextWidth(self.viewport().width())
        self._ajustar_alto()

    def _ajustar_alto(self, *_args) -> None:
        alto = ceil(self.document().size().height()) + self._extra_alto
        if self.height() != alto:
            self.setFixedHeight(alto)


class PanelMensajes(QScrollArea):
    recordar_solicitado = Signal(str, str)

    def __init__(self, parametros: dict, parent=None) -> None:
        super().__init__(parent)
        self._parametros = parametros
        self._claves = None
        self._partes = []
        self._burbujas = []
        self._botones_recordar = []
        self._recordar_habilitado = True
        self.setObjectName("mensajes_chat")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        lienzo = QWidget(self)
        lienzo.setObjectName("lienzo_mensajes")
        self._layout = QVBoxLayout(lienzo)
        margen = parametros["limites"]["burbuja_margen"]
        self._layout.setContentsMargins(margen, margen, margen, margen)
        self._layout.setSpacing(parametros["limites"]["burbuja_separacion"])
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setWidget(lienzo)
        self.verticalScrollBar().rangeChanged.connect(lambda *_: self._bajar())

    def mostrar(self, mensajes: list[dict], modelo: str) -> None:
        claves = tuple((m["id"], m["rol"], m["texto"], m["estado"], m.get("modelo", modelo)) for m in mensajes)
        if claves == self._claves:
            return
        self._claves = claves
        while self._layout.count():
            self._layout.takeAt(0).widget().deleteLater()
        self._burbujas.clear()
        self._botones_recordar.clear()
        self._partes.clear()
        textos, limites = self._parametros["textos"], self._parametros["limites"]
        for mensaje in mensajes:
            usuario = mensaje["rol"] == "user"
            autor = textos["usuario"] if usuario else (mensaje.get("modelo") or modelo or textos["modelo_desconocido"])
            fila = QWidget(self.widget())
            fila.setObjectName("fila_mensaje")
            fila.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            distribucion = QHBoxLayout(fila)
            distribucion.setContentsMargins(0, 0, 0, 0)
            burbuja = QFrame(fila)
            burbuja.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            burbuja.setObjectName("burbuja_usuario" if usuario else "burbuja_asistente")
            columna = QVBoxLayout(burbuja)
            columna.setAlignment(Qt.AlignmentFlag.AlignTop)
            margen = limites["burbuja_margen"]
            columna.setContentsMargins(margen, margen, margen, margen)
            etiqueta = QLabel(autor, burbuja)
            etiqueta.setTextFormat(Qt.TextFormat.PlainText)
            etiqueta.setWordWrap(True)
            etiqueta.setObjectName("autor_mensaje")
            cabecera = QHBoxLayout()
            cabecera.setSpacing(limites["burbuja_separacion"])
            cabecera.addWidget(etiqueta, 1)
            columna.addLayout(cabecera)
            cuerpo = TextoMensaje(mensaje["texto"], limites["burbuja_extra_alto"], burbuja)
            columna.addWidget(cuerpo)
            if mensaje["estado"] == "completo":
                boton = QPushButton(textos["recordar"], burbuja)
                boton.setObjectName("recordar_mensaje")
                boton.setToolTip(textos["recordar_ayuda"])
                boton.setAccessibleName(textos["recordar_accesible"].format(autor=autor))
                boton.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                boton.setEnabled(self._recordar_habilitado)
                boton.clicked.connect(lambda _=False, i=mensaje["id"], c=cuerpo: self._recordar(i, c))
                cabecera.addWidget(boton, 0, Qt.AlignmentFlag.AlignTop)
                self._botones_recordar.append(boton)
            self._partes.append(autor + "\n" + mensaje["texto"])
            if mensaje["estado"] != "completo":
                aviso = {"generando": textos["generando"], "en_curso": textos["esperando_respuesta"]}.get(
                    mensaje["estado"], textos["pendiente"])
                estado = QLabel(aviso, burbuja)
                estado.setWordWrap(True)
                columna.addWidget(estado)
                self._partes.append(aviso)
            if usuario:
                distribucion.addStretch()
            distribucion.addWidget(burbuja)
            if not usuario:
                distribucion.addStretch()
            self._layout.addWidget(fila)
            cuerpo.ensurePolished()
            etiqueta.ensurePolished()
            natural = max(cuerpo.fontMetrics().horizontalAdvance(linea)
                          for linea in (mensaje["texto"].splitlines() or [""]))
            ancho_autor = ceil(QFontMetricsF(etiqueta.font()).horizontalAdvance(autor))
            natural = max(natural, ancho_autor) + margen * 2
            self._burbujas.append((burbuja, max(limites["burbuja_ancho_minimo"], natural)))
        self._adaptar()
        QTimer.singleShot(0, self._bajar)

    def _recordar(self, identidad: str, cuerpo: TextoMensaje) -> None:
        seleccionado = cuerpo.textCursor().selectedText().replace("\u2029", "\n")
        self.recordar_solicitado.emit(identidad, seleccionado or cuerpo.toPlainText())

    def permitir_recordar(self, permitir: bool) -> None:
        self._recordar_habilitado = permitir
        for boton in self._botones_recordar:
            boton.setEnabled(permitir)

    def actualizar_ultimo(self, texto: str) -> None:
        """Actualiza solo el cuerpo en curso, sin reconstruir el historial visible."""
        if not self._burbujas:
            return
        burbuja, _ = self._burbujas[-1]
        cuerpo = burbuja.findChild(TextoMensaje)
        anterior = cuerpo.toPlainText()
        if texto.startswith(anterior):
            cursor = QTextCursor(cuerpo.document())
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(texto[len(anterior):])
        else:
            cuerpo.setPlainText(texto)
        autor = burbuja.findChild(QLabel, "autor_mensaje").text()
        self._partes[-2] = autor + "\n" + texto
        margen = self._parametros["limites"]["burbuja_margen"]
        natural = max(cuerpo.fontMetrics().horizontalAdvance(linea) for linea in (texto.splitlines() or [""]))
        self._burbujas[-1] = (burbuja, natural + margen * 2)
        self._claves = None
        self._adaptar()

    def _bajar(self) -> None:
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def _adaptar(self) -> None:
        limites = self._parametros["limites"]
        proporcion = limites["burbuja_proporcion_compacta"] if self.viewport().width() < limites["historial_ancho_maximo"] * 2 else limites["burbuja_proporcion_ancho"]
        ancho = max(1, int((self.viewport().width() - limites["burbuja_margen"] * 2) * proporcion))
        for burbuja, natural in self._burbujas:
            margenes = burbuja.layout().contentsMargins()
            etiquetas = burbuja.findChildren(QLabel)
            boton = burbuja.findChild(QPushButton, "recordar_mensaje")
            if boton:
                boton.ensurePolished()
            extra = boton.sizeHint().width() + limites["burbuja_separacion"] if boton else 0
            for etiqueta in etiquetas:
                etiqueta.ensurePolished()
            ancho_autor = max((ceil(QFontMetricsF(e.font()).horizontalAdvance(e.text()))
                               + (extra if e.objectName() == "autor_mensaje" else 0)
                               for e in etiquetas), default=0)
            natural = max(natural, ancho_autor + margenes.left() + margenes.right())
            burbuja.setFixedWidth(min(ancho, natural))
            contenido = max(1, burbuja.width() - margenes.left() - margenes.right())
            for etiqueta in etiquetas:
                disponible = contenido - extra if etiqueta.objectName() == "autor_mensaje" else contenido
                etiqueta.setFixedHeight(max(etiqueta.fontMetrics().height(),
                                            etiqueta.heightForWidth(max(1, disponible))))

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        self._adaptar()

    def toPlainText(self) -> str:
        """Texto literal de los mensajes visibles para copia o accesibilidad."""
        return "\n\n".join(self._partes)
