"""Diálogo para gestión, creación y refinamiento de prompts asistido por Ollama."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
from procesos_ia.dominio.prompts import PeticionRefinamiento, PlantillaPrompt, ResultadoRefinamiento
from procesos_ia.dominio.evaluaciones import resultados_compatibles, resultados_desde_datos
from procesos_ia.interfaz.borradores import GestorBorradores, volcar_datos_editor
from procesos_ia.interfaz.composicion_prompts import construir_interfaz_prompts
from procesos_ia.interfaz.hilos_evaluacion import HiloRefinamiento
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido
from procesos_ia.interfaz.responsivo import ModoPantalla
from procesos_ia.infraestructura.prompts.parametros import cargar_parametros_evaluacion


class DialogoGestionPrompts(QWidget):
    """Interfaz para administrar y refinar plantillas de prompts integrada en la ventana."""

    plantilla_seleccionada = Signal(PlantillaPrompt)
    plantilla_guardada = Signal(PlantillaPrompt)
    volver_solicitado = Signal()

    def __init__(
        self,
        servicio_prompts: ServicioCatalogoPrompts,
        modelo_activo: str = "qwen2.5:1.5b",
        gestor_borradores: GestorBorradores | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Catálogo y Refinador de Prompts")
        self._borradores = gestor_borradores or GestorBorradores()
        self._textos = cargar_parametros_evaluacion()
        self._hilo_refinamiento = None
        self._cerrar_pendiente = False
        self._servicio = servicio_prompts
        from procesos_ia.aplicacion.ia_web.comun.prompts_ia_web import asegurar_plantillas_ia_web
        asegurar_plantillas_ia_web(self._servicio)
        self._modelo_activo = modelo_activo
        self._plantilla_actual: PlantillaPrompt | None = None
        self._iniciar_ui()
        self._cargar_modelos()
        self._cargar_lista()

    def _iniciar_ui(self) -> None:
        construir_interfaz_prompts(self)

    def _cargar_modelos(self) -> None:
        self.combo_modelos.clear()
        try:
            from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
            modelos = ClienteHttpOllama().listar_modelos(tiempo_limite=1.5, reintentos=0)
            nombres = [m.nombre for m in modelos if m.nombre]
            if nombres:
                self.combo_modelos.addItems(nombres)
                if self._modelo_activo in nombres:
                    self.combo_modelos.setCurrentText(self._modelo_activo)
                else:
                    self._modelo_activo = nombres[0]
            else:
                self.combo_modelos.addItem(self._modelo_activo or "qwen2.5:1.5b")
        except Exception:
            self.combo_modelos.addItem(self._modelo_activo or "qwen2.5:1.5b")

    def _al_cambiar_modelo(self, modelo: str) -> None:
        if modelo:
            self._modelo_activo = modelo

    def _cargar_lista(self, identificador: str | None = None) -> None:
        plantillas = self._servicio.listar_plantillas(categoria=self.combo_filtro.currentData() or None)
        self.lista_prompts.blockSignals(True)
        self.lista_prompts.clear()
        for p in plantillas:
            item = QListWidgetItem(f"{p.titulo} [{p.categoria}]", self.lista_prompts)
            item.setData(Qt.ItemDataRole.UserRole, p.identificador)
        self.lista_prompts.blockSignals(False)
        if plantillas:
            fila = next((i for i, p in enumerate(plantillas) if p.identificador == identificador), 0)
            self.lista_prompts.setCurrentRow(fila)
            self._seleccionar_plantilla(fila)

    def _seleccionar_plantilla(self, fila: int) -> None:
        item = self.lista_prompts.item(fila)
        if item is None:
            return
        id_sel = item.data(Qt.ItemDataRole.UserRole)
        p = self._servicio.obtener_plantilla(str(id_sel)) if id_sel else None
        if p is not None:
            self._plantilla_actual = p
            self.input_titulo.setText(p.titulo)
            self.input_categoria.setText(p.categoria)
            self.input_descripcion.setText(p.descripcion)
            self.editor_resultados.cargar(resultados_compatibles(p))
            self.texto_contenido.setPlainText(p.contenido)

    def _crear_nuevo(self) -> None:
        self._plantilla_actual = None
        self.input_titulo.setText("Nueva Plantilla")
        self.input_categoria.setText(self.combo_filtro.currentData() or "ia_web")
        self.input_descripcion.clear()
        self.editor_resultados.cargar(())
        self.texto_contenido.clear()

    def _insertar_delimitador(self) -> None:
        from procesos_ia.aplicacion.ia_web.comun.prompts_ia_web import AYUDA_DELIMITADOR_COLUMNAS
        self.texto_contenido.insertPlainText(f"\n{AYUDA_DELIMITADOR_COLUMNAS}\n")

    def _guardar_actual(self, mostrar_aviso: bool = True) -> PlantillaPrompt | None:
        titulo, contenido = self.input_titulo.text().strip(), self.texto_contenido.toPlainText().strip()
        categoria = self.input_categoria.text().strip() or "ia_web"
        descripcion = self.input_descripcion.text().strip()
        if not titulo or not contenido:
            self.estado_refinamiento.setText("[ALERTA] El título y el contenido son obligatorios.")
            return None
        id_existente = self._plantilla_actual.identificador if self._plantilla_actual else None
        try:
            resultados = self.editor_resultados.obtener()
            guardada = self._servicio.crear_plantilla(
                titulo=titulo, contenido=contenido, categoria=categoria,
                descripcion=descripcion, resultados=resultados, identificador=id_existente,
            )
            self._plantilla_actual = guardada
            self._borradores.limpiar_prompts(); self._borradores.limpiar_preparacion()
            self._cargar_lista(guardada.identificador)
            self.plantilla_guardada.emit(guardada)
            if mostrar_aviso:
                QMessageBox.information(self, "Guardado", f"[OK] Plantilla '{titulo}' guardada exitosamente.")
            return guardada
        except Exception as error:
            QMessageBox.critical(self, "Error", f"[ERROR] No se pudo guardar: {error}")
            return None

    def _eliminar_actual(self) -> None:
        if not self._plantilla_actual:
            return
        btn = QMessageBox.question(
            self, "Confirmar eliminación", f"¿Desea eliminar la plantilla '{self._plantilla_actual.titulo}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if btn == QMessageBox.StandardButton.Yes:
            self._servicio.eliminar_plantilla(self._plantilla_actual.identificador)
            self._crear_nuevo()
            self._cargar_lista()

    def _cambiar_estado_controles(self, habilitado: bool) -> None:
        for w in (self.btn_refinar, self.btn_guardar, self.btn_usar, self.btn_nuevo,
                  self.btn_eliminar, self.combo_filtro, self.lista_prompts, self.editor_resultados, self.combo_modelos):
            w.setEnabled(habilitado)
        self.texto_contenido.setReadOnly(not habilitado)
        self.setCursor(Qt.CursorShape.ArrowCursor if habilitado else Qt.CursorShape.WaitCursor)

    def _refinar_con_ia(self) -> None:
        if self._hilo_refinamiento is not None:
            return
        modelo = self.combo_modelos.currentText().strip() or self._modelo_activo
        if not modelo or "detenido" in modelo.lower():
            self.estado_refinamiento.setText("[ALERTA] Seleccione o descargue un modelo local en Ollama.")
            return
        idea = self.texto_contenido.toPlainText().strip()
        if not idea:
            self.estado_refinamiento.setText("[ALERTA] Ingrese una idea o criterio en las instrucciones.")
            return
        self.estado_refinamiento.setText(f"[EN PROCESO] Consultando modelo '{modelo}'...")
        self._cambiar_estado_controles(False)
        h = HiloRefinamiento(self._servicio, PeticionRefinamiento(idea_usuario=idea), modelo, self)
        self._hilo_refinamiento = h
        h.senial_resultado.connect(self._al_refinar)
        h.senial_error.connect(self._al_error_refinamiento)
        h.finished.connect(self._al_terminar_refinamiento)
        h.start()

    def _al_refinar(self, resultado: ResultadoRefinamiento) -> None:
        self.texto_contenido.setPlainText(resultado.prompt_refinado)
        self.editor_resultados.cargar(resultado.resultados)
        self.estado_refinamiento.setText(self._textos.get("refinamiento_listo", "[OK] Sugerencia generada."))

    def _al_error_refinamiento(self, error: str) -> None:
        self.estado_refinamiento.setText(f"[ERROR] {error}")
        QMessageBox.warning(self, "Aviso de refinamiento", f"[ERROR] {error}")

    def _al_terminar_refinamiento(self) -> None:
        if self._hilo_refinamiento is not None:
            self._hilo_refinamiento.deleteLater()
            self._hilo_refinamiento = None
        self._cambiar_estado_controles(True)
        if self._cerrar_pendiente:
            self._cerrar_pendiente = False
            self._al_volver()

    def _al_volver(self) -> None:
        if self._hilo_refinamiento is not None:
            self._cerrar_pendiente = True
        else:
            self.guardar_borrador()
            self.volver_solicitado.emit()

    def guardar_borrador(self) -> None:
        self._borradores.guardar_prompts(
            self.input_titulo.text().strip(), self.input_categoria.text().strip(),
            self.input_descripcion.text().strip(), self.texto_contenido.toPlainText(),
            volcar_datos_editor(self.editor_resultados.tabla),
            self._plantilla_actual.identificador if self._plantilla_actual else None,
        )

    def restaurar_borrador_si_existe(self) -> bool:
        if not self._borradores.tiene_borrador_prompts():
            return False
        b = self._borradores.obtener_prompts()
        identificador = b.get("identificador_activo")
        self._plantilla_actual = next((p for p in self._servicio.listar_plantillas() if p.identificador == identificador), None)
        self.input_titulo.setText(b.get("titulo", ""))
        self.input_categoria.setText(b.get("categoria", "general"))
        self.input_descripcion.setText(b.get("descripcion", ""))
        self.texto_contenido.setPlainText(b.get("contenido", ""))
        if "resultados_datos" in b:
            try:
                self.editor_resultados.cargar(resultados_desde_datos(b["resultados_datos"]))
            except Exception:
                pass
        self.estado_refinamiento.setText("[INFO] Borrador temporal restaurado.")
        return True

    def limpiar_borrador(self) -> None:
        self._borradores.limpiar_prompts()
        self._crear_nuevo()
        self.estado_refinamiento.setText("[INFO] Borrador descartado. Formulario limpio desde cero.")

    def _usar_plantilla(self) -> None:
        plantilla = self._guardar_actual(mostrar_aviso=False)
        if plantilla is not None:
            self._borradores.limpiar_prompts()
            self._borradores.limpiar_preparacion()
            self.plantilla_seleccionada.emit(plantilla)
            self.volver_solicitado.emit()

    def _notificar_estado(self, msj: str) -> None:
        if hasattr(self, "estado_refinamiento") and self.estado_refinamiento:
            self.estado_refinamiento.setText(msj)

    def exec(self) -> int:
        return 1

    def reject(self) -> None:
        self._al_volver()

    def accept(self) -> None:
        self.volver_solicitado.emit()

    def adaptar_modo(self, modo: ModoPantalla) -> None:
        self.splitter.setOrientation(Qt.Orientation.Vertical if modo == ModoPantalla.COMPACTO else Qt.Orientation.Horizontal)
