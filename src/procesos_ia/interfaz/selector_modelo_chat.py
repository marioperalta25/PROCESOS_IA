"""Selección sin inferencia para chats nuevos y modelo fijo para historiales."""

from PySide6.QtCore import QObject


class SelectorModeloChat(QObject):
    def __init__(self, vista, catalogo) -> None:
        super().__init__(vista)
        self._vista, self._catalogo = vista, catalogo
        vista.combo_modelos.currentIndexChanged.connect(self._cambiar)

    def preparar_nuevo(self) -> None:
        modelo = self._vista._opciones()[0]
        self._vista._datos["modelo"] = modelo if modelo in self._catalogo() else ""

    def actualizar(self) -> None:
        vista = self._vista
        textos = vista.parametros["textos"]
        datos = vista._datos
        seleccionado = datos.get("modelo", "")
        nombres = self._catalogo()
        combo = vista.combo_modelos
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(textos["elegir_modelo"], "")
        for nombre in nombres:
            combo.addItem(nombre, nombre)
        if seleccionado and seleccionado not in nombres:
            combo.addItem(seleccionado, seleccionado)
        combo.setCurrentIndex(max(0, combo.findData(seleccionado)))
        combo.blockSignals(False)
        fijo = bool(datos["mensajes"])
        combo.setEnabled(not fijo and vista._hilo is None)
        combo.setVisible(not fijo)
        vista.modelo.setVisible(fijo)
        combo.setToolTip(textos["modelo_fijo"])
        vista.modelo.setText(textos["modelo"].format(modelo=seleccionado or textos["elegir_modelo"]))
        if fijo and not seleccionado:
            vista.banner.mostrar_alerta(textos["modelo_antiguo"])
        elif seleccionado and seleccionado not in nombres:
            vista.banner.mostrar_alerta(textos["modelo_ausente"])

    def _cambiar(self, indice: int) -> None:
        vista = self._vista
        if vista._hilo is None and not vista._datos["mensajes"]:
            vista._datos["modelo"] = vista.combo_modelos.itemData(indice) or ""
            vista.banner.mostrar_info(vista.parametros["textos"]["modelo_fijo"])
            self.actualizar()

    def disponible(self) -> bool:
        modelo = self._vista._datos.get("modelo", "")
        return bool(modelo and modelo in self._catalogo())
