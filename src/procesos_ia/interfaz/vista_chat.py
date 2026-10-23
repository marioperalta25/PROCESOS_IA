"""Vista de conversación integrada, con borradores y memoria por identidad."""

from PySide6.QtCore import QEvent, Qt, Signal, Slot
from PySide6.QtWidgets import QListWidgetItem, QWidget

from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.interfaz.chat_composicion import construir_chat
from procesos_ia.interfaz.chat_hilo import HiloChat
from procesos_ia.interfaz.chat_memoria import MemoriaChat
from procesos_ia.interfaz.chat_progreso import ProgresoChat
from procesos_ia.interfaz.responsivo import ModoPantalla
from procesos_ia.interfaz.selector_modelo_chat import SelectorModeloChat


class VistaChat(QWidget):
    volver_solicitado = Signal()
    solicitar_actualizacion_modelos = Signal()

    def __init__(self, servicio, parametros: dict, opciones, ocupado, parent=None, *, catalogo=None) -> None:
        super().__init__(parent)
        self.servicio, self.parametros = servicio, parametros
        self.repositorio = servicio.repositorio
        self._opciones, self._ocupado = opciones, ocupado
        self._hilo = None
        self._volver_pendiente = False
        self._borradores = {}
        self._temporales = {}
        self._datos = self.repositorio.nuevo()
        self._edicion = ""
        self._identidad_peticion = None
        self._componiendo = False
        self._compacto = False
        self._progreso = ProgresoChat(self)
        construir_chat(self, parametros["textos"])
        self._memoria = MemoriaChat(self)
        self._selector = SelectorModeloChat(self, catalogo or (lambda: [self._opciones()[0]]))
        self._selector.preparar_nuevo()
        self.setStyleSheet(parametros["estilo"]["hoja"])
        self._refrescar_lista()
        self._pintar()

    def _refrescar_lista(self) -> None:
        try:
            chats = self.repositorio.listar()
            persistidos = {chat["id"] for chat in chats}
            for identidad in persistidos:
                self._temporales.pop(identidad, None)
            temporales = [{"id": identidad, "titulo": self._borradores[identidad].splitlines()[0][
                :self.parametros["limites"]["titulo_caracteres"]]} for identidad in self._temporales
                if identidad not in persistidos and self._borradores.get(identidad)]
            chats = list(reversed(temporales)) + chats
            self.lista.blockSignals(True)
            self.lista.clear()
            for chat in chats:
                item = QListWidgetItem(chat["titulo"], self.lista)
                item.setData(Qt.ItemDataRole.UserRole, chat["id"])
                item.setToolTip(chat["titulo"])
                if chat["id"] == self._datos["id"]:
                    self.lista.setCurrentItem(item)
            limites = self.parametros["limites"]
            self.uso.setText(self.parametros["textos"]["uso"].format(
                usado=self.repositorio.uso() / limites["bytes_por_mb"],
                limite=limites["historial_bytes"] / limites["bytes_por_mb"]))
        except (OSError, ErrorProcesamiento) as error:
            self.banner.mostrar_error(str(error))
        finally:
            self.lista.blockSignals(False)

    def _guardar_borrador(self) -> None:
        identidad = self._datos["id"]
        texto = self.entrada.toPlainText()
        limites = self.parametros["limites"]
        total = sum(len(v.encode("utf-8")) for k, v in self._borradores.items() if k != identidad)
        error = "entrada_grande" if len(texto.encode("utf-8")) > limites["entrada_bytes"] else None
        if total + len(texto.encode("utf-8")) > limites["borradores_bytes"]:
            error = "borradores_llenos"
        if (not self._datos["actualizado"] and identidad not in self._temporales
                and self.lista.count() >= limites["conversaciones"]):
            error = "borradores_llenos"
        if error:
            self.entrada.blockSignals(True)
            self.entrada.setPlainText(self._borradores.get(identidad, ""))
            self.entrada.blockSignals(False)
            self.banner.mostrar_alerta(self.parametros["textos"][error])
            return
        if texto:
            self._borradores[identidad] = texto
            if not self._datos["actualizado"]:
                self._temporales[identidad] = self._datos
        else:
            self._borradores.pop(identidad, None)
            self._temporales.pop(identidad, None)

    def _pintar(self) -> None:
        textos = self.parametros["textos"]
        self.titulo.setText(self._datos["titulo"])
        self.entrada.blockSignals(True)
        self.entrada.setPlainText(self._borradores.get(self._datos["id"], ""))
        self.entrada.blockSignals(False)
        self._selector.actualizar()
        ultimos = self._progreso.mensajes(self._datos)[-self.parametros["limites"]["mensajes_visibles"]:]
        self.transcripcion.mostrar(ultimos, self._datos.get("modelo", ""))
        activo = self._hilo is not None
        self.transcripcion.permitir_recordar(not activo)
        for control in (self.btn_borrar, self.btn_renombrar, self.btn_memoria, self.barra_nav.btn_limpiar):
            control.setEnabled(not activo)
        self.btn_enviar.setText(textos["detener"] if activo else textos["enviar"])
        self.btn_reintentar.setVisible(bool(ultimos and ultimos[-1]["rol"] == "user"
                                           and ultimos[-1]["estado"] != "completo"))
        self.btn_reintentar.setEnabled(not activo)

    def _seleccionar(self, fila: int) -> None:
        if fila < 0:
            return
        try:
            identidad = self.lista.item(fila).data(Qt.ItemDataRole.UserRole)
            datos = self._temporales.get(identidad) or self.repositorio.leer(identidad)
            self._datos = datos
            self._mostrar_conversacion()
            self._pintar()
        except ErrorProcesamiento as error:
            self.banner.mostrar_error(str(error))

    def _nuevo(self) -> None:
        if self._hilo is None:
            self._datos = self.repositorio.nuevo()
            self._selector.preparar_nuevo()
            self._mostrar_conversacion()
            self._refrescar_lista()
            self._pintar()

    def _editar_nombre(self) -> None:
        self._mostrar_editor("nombre", self.parametros["textos"]["renombrar"])
        self.nombre.setText(self._datos["titulo"])

    def _editar_memoria(self) -> None:
        self._mostrar_editor("memoria", self.parametros["textos"]["guardar_memoria"])
        self.resumen.setPlainText(self._datos["resumen"])

    def _pedir_borrado(self) -> None:
        self._mostrar_editor("borrar", self.parametros["textos"]["confirmar_borrado"])

    def _mostrar_editor(self, modo: str, boton: str) -> None:
        self._edicion = modo
        self.nombre.setVisible(modo == "nombre")
        self.resumen.setVisible(modo == "memoria")
        self.btn_confirmar.setText(boton)
        self.contenido.setCurrentWidget(self.editor)

    def _cerrar_editor(self) -> None:
        self.contenido.setCurrentWidget(self.transcripcion)

    def _mostrar_conversacion(self) -> None:
        self._cerrar_editor()
        if self._compacto:
            self.lateral.hide()
            self.panel_conversacion.show()

    def _confirmar_edicion(self) -> None:
        if self._hilo is not None:
            return
        try:
            if self._edicion == "borrar":
                identidad = self._datos["id"]
                self.repositorio.borrar(identidad)
                self._borradores.pop(identidad, None)
                self._temporales.pop(identidad, None)
                self._nuevo()
            else:
                from copy import deepcopy
                datos = deepcopy(self._datos)
                if self._edicion == "nombre":
                    nombre = self.nombre.text().strip()
                    if not nombre:
                        raise ErrorProcesamiento(self.parametros["textos"]["nombre_invalido"])
                    datos["titulo"] = nombre
                    self.repositorio.guardar(datos, version_esperada=self._datos["actualizado"])
                else:
                    resumen = self.resumen.toPlainText().strip()
                    datos = self.servicio.guardar_memoria(self._datos, resumen)
                self._datos = datos
                self._temporales.pop(datos["id"], None)
            self._cerrar_editor()
            self._refrescar_lista()
            self._pintar()
        except (OSError, ErrorProcesamiento) as error:
            self.banner.mostrar_error(str(error))

    def _enviar(self, reintentar: bool = False) -> None:
        textos = self.parametros["textos"]
        if self._hilo is not None:
            self._hilo.cancelar()
            self.banner.mostrar_info(textos["volviendo"])
            return
        if self._ocupado():
            self.banner.mostrar_alerta(textos["ocupado"])
            return
        _, contexto, temperatura = self._opciones()
        modelo = self._datos.get("modelo", "")
        contexto = self._datos.get("contexto", contexto)
        temperatura = self._datos.get("temperatura", temperatura)
        if not modelo:
            self.banner.mostrar_alerta(textos["modelo_antiguo"] if self._datos["mensajes"] else textos["sin_modelo"])
            return
        if not self._selector.disponible():
            self.banner.mostrar_alerta(textos["modelo_ausente"])
            return
        entrada = self._datos["mensajes"][-1]["texto"] if reintentar else self.entrada.toPlainText().strip()
        if not entrada:
            return
        self._cerrar_editor()
        self._identidad_peticion = self._datos["id"]
        self._borrador_enviado = self._borradores.get(self._identidad_peticion, "")
        self._hilo = HiloChat(self.servicio, (self._datos, entrada, modelo, contexto, temperatura, reintentar), self)
        self._progreso.iniciar(self._identidad_peticion, entrada, reintentar)
        self._hilo.fragmento.connect(self._progreso.actualizar, Qt.ConnectionType.QueuedConnection)
        self._hilo.resultado.connect(self._al_resultado)
        self._hilo.error.connect(self._al_error)
        self._hilo.finished.connect(self._al_terminar)
        self.banner.mostrar_en_proceso(textos["generando"])
        self._pintar()
        self._hilo.start()

    @Slot(object, str)
    def _al_resultado(self, datos: dict, aviso: str) -> None:
        self._progreso.finalizar()
        identidad = datos["id"]
        self._temporales.pop(identidad, None)
        if self._borradores.get(identidad, "") == self._borrador_enviado:
            self._borradores.pop(identidad, None)
        if self._datos["id"] == identidad:
            self._datos = datos
        self.banner.mostrar_info(aviso)

    @Slot(str)
    def _al_error(self, error: str) -> None:
        self._progreso.finalizar()
        if self._identidad_peticion == self._datos["id"]:
            try:
                if self.repositorio.existe(self._datos["id"]):
                    self._datos = self.repositorio.leer(self._datos["id"])
            except ErrorProcesamiento:
                pass
        self.banner.mostrar_error(error)

    @Slot()
    def _al_terminar(self) -> None:
        self._hilo.deleteLater()
        self._hilo = None
        self._refrescar_lista()
        self._pintar()
        if self._volver_pendiente:
            self._volver_pendiente = False
            self.volver_solicitado.emit()

    def _volver(self) -> None:
        if self._hilo is not None:
            self._volver_pendiente = True
            self._hilo.cancelar()
            self.banner.mostrar_info(self.parametros["textos"]["volviendo"])
        else:
            self.volver_solicitado.emit()

    def adaptar_modo(self, modo: ModoPantalla) -> None:
        compacto = modo == ModoPantalla.COMPACTO
        self._compacto = compacto
        self.lateral.setVisible(not compacto)
        self.panel_conversacion.show()
        self.lateral.setMaximumWidth(self.parametros["limites"]["historial_ancho_maximo"] if not compacto
                                     else self.maximumWidth())
        self.btn_historial.setVisible(compacto)
        self.divisor.setOrientation(Qt.Orientation.Vertical if compacto else Qt.Orientation.Horizontal)

    def _alternar_historial(self) -> None:
        mostrar = self.lateral.isHidden()
        self.lateral.setVisible(mostrar)
        self.panel_conversacion.setVisible(not mostrar)

    def eventFilter(self, objeto, evento) -> bool:
        if objeto is self.entrada and evento.type() == QEvent.Type.InputMethod:
            self._componiendo = bool(evento.preeditString())
        if (objeto is self.entrada and evento.type() == QEvent.Type.KeyPress
                and evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and not self._componiendo
                and not evento.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self._enviar()
            return True
        return super().eventFilter(objeto, evento)
