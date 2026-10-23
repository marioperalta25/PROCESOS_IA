"""Correspondencias revisables y muestra previa a la escritura de un trabajo."""

from dataclasses import replace
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from procesos_ia.aplicacion.contratos import ServicioInferenciaProtocol
from procesos_ia.aplicacion.muestra import FilaMuestra
from procesos_ia.dominio.modelos import ConfiguracionTrabajo
from procesos_ia.dominio.prompts import PlantillaPrompt
from procesos_ia.dominio.evaluaciones import (
    ContratoEvaluacion, VinculoEntrada, VinculoSalida, resultados_compatibles,
)
from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.infraestructura.prompts.parametros import cargar_parametros_evaluacion
from procesos_ia.interfaz.borradores import GestorBorradores
from procesos_ia.interfaz.componentes.banner_notificacion import BannerNotificacion
from procesos_ia.interfaz.componentes.barra_navegacion import BarraNavegacionSubvista
from procesos_ia.interfaz.hilos_evaluacion import HiloMuestra
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido
from procesos_ia.interfaz.responsivo import ModoPantalla


class DialogoPrepararTrabajo(QWidget):
    volver_solicitado = Signal()
    trabajo_confirmado = Signal(object)

    def __init__(
        self, configuracion: ConfiguracionTrabajo, plantilla: PlantillaPrompt,
        encabezados: tuple[str, ...], inferencia: ServicioInferenciaProtocol,
        gestor_borradores: GestorBorradores | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._base = configuracion
        self._plantilla = plantilla
        self._resultados = resultados_compatibles(plantilla)
        self._encabezados = encabezados
        self._inferencia = inferencia
        self._borradores = gestor_borradores or GestorBorradores()
        self._textos = cargar_parametros_evaluacion()
        self._hilo: HiloMuestra | None = None
        self._cerrar_pendiente = False
        self._muestra_ejecutada = False
        self.configuracion_aprobada: ConfiguracionTrabajo | None = None
        self.setWindowTitle(self._textos["titulo_preparacion"])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.barra_nav = BarraNavegacionSubvista(
            self._textos["titulo_preparacion"], "Restablecer de 0", self,
        )
        self.barra_nav.volver_solicitado.connect(self._al_volver)
        self.barra_nav.limpiar_solicitado.connect(self.limpiar_borrador)
        layout.addWidget(self.barra_nav)

        ayuda = QLabel(self._textos["ayuda_preparacion"], self)
        ayuda.setWordWrap(True)
        layout.addWidget(ayuda)

        roles = tuple(dict.fromkeys(e for r in self._resultados for e in r.entradas))
        self.tabla_entradas = QTableWidget(len(roles), 2, self)
        self.tabla_entradas.setHorizontalHeaderLabels(self._textos["tabla_entradas"])
        self.tabla_entradas.horizontalHeader().setStretchLastSection(True)
        self.tabla_entradas.setColumnWidth(0, 180)
        self.entradas = {}
        for fila, rol in enumerate(roles):
            self.tabla_entradas.setItem(fila, 0, self._celda_fija(rol))
            lista = QListWidget(self)
            for columna in configuracion.columnas_evaluar:
                item = QListWidgetItem(columna, lista)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                sugerida = columna == rol or rol == "datos"
                item.setCheckState(Qt.CheckState.Checked if sugerida else Qt.CheckState.Unchecked)
            lista.itemChanged.connect(self._invalidar_muestra)
            self.entradas[rol] = lista
            self.tabla_entradas.setCellWidget(fila, 1, lista)
            self.tabla_entradas.setRowHeight(fila, self._textos["alto_fila_entrada"])
        layout.addWidget(self.tabla_entradas)

        self.tabla_salidas = QTableWidget(len(self._resultados), 2, self)
        self.tabla_salidas.setHorizontalHeaderLabels(self._textos["tabla_salidas"])
        self.tabla_salidas.horizontalHeader().setStretchLastSection(True)
        self.tabla_salidas.setColumnWidth(0, 240)
        self.salidas = {}
        for fila, resultado in enumerate(self._resultados):
            celda = self._celda_fija(resultado.clave)
            celda.setToolTip(f"{resultado.criterio}\n{resultado.tipo}: {', '.join(resultado.opciones)}")
            self.tabla_salidas.setItem(fila, 0, celda)
            destino = resultado.clave if not plantilla.resultados else f"{resultado.clave}_ia"
            campo = QLineEdit(destino, self)
            campo.textChanged.connect(self._invalidar_muestra)
            self.salidas[resultado.clave] = campo
            self.tabla_salidas.setCellWidget(fila, 1, campo)
        layout.addWidget(self.tabla_salidas)

        self.banner = BannerNotificacion(self)
        self.banner.mostrar_info(self._textos["muestra_pendiente"])
        self.estado = self.banner._label_mensaje
        layout.addWidget(self.banner)

        self.tabla_muestra = QTableWidget(0, 4, self)
        self.tabla_muestra.setHorizontalHeaderLabels(self._textos["tabla_muestra"])
        self.tabla_muestra.horizontalHeader().setStretchLastSection(True)
        self.tabla_muestra.setColumnWidth(0, 45)
        self.tabla_muestra.setColumnWidth(1, 280)
        self.tabla_muestra.setColumnWidth(2, 380)
        layout.addWidget(self.tabla_muestra)

        acciones = QHBoxLayout()
        self.btn_muestra = QPushButton(self._textos["probar_muestra"], self)
        conectar_boton_protegido(self.btn_muestra, self._probar_muestra, "[INFO] Evaluando muestra previa...", self.banner.mostrar_info, 1000)
        self.btn_iniciar = QPushButton(self._textos["iniciar"], self)
        self.btn_iniciar.setObjectName("btn_principal")
        conectar_boton_protegido(self.btn_iniciar, self.accept, "[INFO] Confirmando e iniciando procesamiento...", self.banner.mostrar_info, 1000)
        volver = QPushButton(self._textos["cancelar"], self)
        conectar_boton_protegido(volver, self.reject, "[INFO] Regresando al menú...", self.banner.mostrar_info, 600)
        for boton in (self.btn_muestra, self.btn_iniciar, volver):
            acciones.addWidget(boton)
        layout.addLayout(acciones)

    @staticmethod
    def _celda_fija(texto: str) -> QTableWidgetItem:
        item = QTableWidgetItem(texto)
        item.setToolTip(texto)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def obtener_configuracion(self) -> ConfiguracionTrabajo:
        entradas = tuple(VinculoEntrada(rol, tuple(
            lista.item(i).text() for i in range(lista.count())
            if lista.item(i).checkState() == Qt.CheckState.Checked
        )) for rol, lista in self.entradas.items())
        salidas = tuple(VinculoSalida(clave, campo.text().strip()) for clave, campo in self.salidas.items())
        contrato = ContratoEvaluacion(self._resultados, entradas, salidas)
        contrato.validar(self._encabezados)
        configuracion = replace(
            self._base, contrato_evaluacion=contrato,
            columnas_evaluar=tuple(dict.fromkeys(c for e in entradas for c in e.columnas)),
            columnas_salida_modelo=tuple(s.columna for s in salidas),
            identificador_plantilla=self._plantilla.identificador,
            version_plantilla=self._plantilla.version,
        )
        configuracion.validar_esquema_salida()
        return configuracion

    @staticmethod
    def _formatear_campos(datos: dict) -> str:
        if not datos:
            return "(Sin datos)"
        return "\n".join(f"{clave}: {valor}" for clave, valor in datos.items())

    def _invalidar_muestra(self, *_args) -> None:
        self.tabla_muestra.setRowCount(0)
        clave = "muestra_desactualizada" if self._muestra_ejecutada else "muestra_pendiente"
        if self._muestra_ejecutada:
            self.banner.mostrar_alerta(self._textos[clave])
        else:
            self.banner.mostrar_info(self._textos[clave])

    def _probar_muestra(self) -> None:
        if self._hilo is not None:
            return
        try:
            configuracion = self.obtener_configuracion()
        except ErrorProcesamiento as error:
            self.banner.mostrar_error(str(error))
            return
        self.tabla_muestra.setRowCount(0)
        self.banner.mostrar_en_proceso(self._textos["muestra_procesando"])
        self.setCursor(Qt.CursorShape.WaitCursor)
        for w in (self.tabla_entradas, self.tabla_salidas, self.btn_muestra, self.btn_iniciar):
            w.setEnabled(False)
        self._hilo = HiloMuestra(configuracion, self._inferencia, self._textos["filas_muestra"], self)
        self._hilo.senial_resultado.connect(self._mostrar_muestra)
        self._hilo.senial_error.connect(self._al_error_muestra)
        self._hilo.finished.connect(self._al_terminar)
        self._hilo.start()

    def _al_error_muestra(self, error: str) -> None:
        self.banner.mostrar_error(f"Fallo al evaluar la muestra: {error}")

    def _mostrar_muestra(self, filas: list[FilaMuestra]) -> None:
        self._muestra_ejecutada = True
        self.tabla_muestra.setRowCount(len(filas))
        for indice, fila in enumerate(filas):
            resultado = fila.evaluacion
            datos_evaluados = fila.datos_evaluados if getattr(fila, "datos_evaluados", None) else fila.originales
            valores = (
                str(fila.indice),
                self._formatear_campos(datos_evaluados),
                self._formatear_campos(resultado.salida_estructurada),
                "; ".join(resultado.errores) if resultado.errores else "[OK] Correcto",
            )
            for columna, valor in enumerate(valores):
                self.tabla_muestra.setItem(indice, columna, self._celda_fija(valor))
        self.tabla_muestra.resizeRowsToContents()
        self.banner.mostrar_exito(self._textos.get(
            "muestra_completada",
            "Muestra evaluada con éxito (3 filas analizadas). Inspeccione abajo los datos y respuestas.",
        ))

    def _al_terminar(self) -> None:
        self.unsetCursor()
        if self._hilo is not None:
            self._hilo.deleteLater()
            self._hilo = None
        for w in (self.tabla_entradas, self.tabla_salidas, self.btn_muestra, self.btn_iniciar):
            w.setEnabled(True)
        if self._cerrar_pendiente:
            self._cerrar_pendiente = False
            self.guardar_borrador()
            self.volver_solicitado.emit()

    def adaptar_modo(self, modo: ModoPantalla) -> None:
        """Ajusta anchos de columnas de tablas para visualización óptima según la resolución."""
        c0, s0 = (120, 140) if modo == ModoPantalla.COMPACTO else (180, 240)
        m1, m2 = (180, 220) if modo == ModoPantalla.COMPACTO else (280, 380)
        self.tabla_entradas.setColumnWidth(0, c0)
        self.tabla_salidas.setColumnWidth(0, s0)
        self.tabla_muestra.setColumnWidth(1, m1)
        self.tabla_muestra.setColumnWidth(2, m2)

    def guardar_borrador(self) -> None:
        entradas_dict = {
            rol: [lista.item(i).text() for i in range(lista.count()) if lista.item(i).checkState() == Qt.CheckState.Checked]
            for rol, lista in self.entradas.items()
        }
        salidas_dict = {k: c.text() for k, c in self.salidas.items()}
        self._borradores.guardar_preparacion(entradas_dict, salidas_dict, self._plantilla.identificador)

    def restaurar_borrador_si_existe(self) -> bool:
        if not self._borradores.tiene_borrador_preparacion():
            return False
        b = self._borradores.obtener_preparacion()
        if b.get("identificador_plantilla") and b["identificador_plantilla"] != self._plantilla.identificador:
            return False
        for rol, cols in b.get("asignaciones_entradas", {}).items():
            if rol in self.entradas:
                lista = self.entradas[rol]
                for i in range(lista.count()):
                    lista.item(i).setCheckState(Qt.CheckState.Checked if lista.item(i).text() in cols else Qt.CheckState.Unchecked)
        for clave, dest in b.get("destinos_salidas", {}).items():
            if clave in self.salidas:
                self.salidas[clave].setText(dest)
        self.banner.mostrar_info("[INFO] Se restauraron sus selecciones temporales.")
        return True

    def limpiar_borrador(self) -> None:
        self._borradores.limpiar_preparacion()
        for rol, lista in self.entradas.items():
            for i in range(lista.count()):
                sug = lista.item(i).text() == rol or rol == "datos"
                lista.item(i).setCheckState(Qt.CheckState.Checked if sug else Qt.CheckState.Unchecked)
        for clave, campo in self.salidas.items():
            campo.setText(clave if not self._plantilla.resultados else f"{clave}_ia")
        self.tabla_muestra.setRowCount(0)
        self._muestra_ejecutada = False
        self.banner.mostrar_info(self._textos["muestra_pendiente"])

    def _al_volver(self) -> None:
        if self._hilo is not None:
            self._cerrar_pendiente = True
            self._hilo.cancelar()
            return
        self.guardar_borrador()
        self.volver_solicitado.emit()

    def accept(self) -> None:
        if self._hilo is not None:
            return
        try:
            self.configuracion_aprobada = self.obtener_configuracion()
        except ErrorProcesamiento as error:
            self.banner.mostrar_error(str(error))
            return
        self._borradores.limpiar_preparacion()
        self.trabajo_confirmado.emit(self.configuracion_aprobada)
        self.volver_solicitado.emit()

    def reject(self) -> None:
        self._al_volver()

    def exec(self) -> int:
        return 1

    def closeEvent(self, evento: QCloseEvent) -> None:
        if self._hilo is not None:
            evento.ignore()
            self._al_volver()
        else:
            super().closeEvent(evento)
