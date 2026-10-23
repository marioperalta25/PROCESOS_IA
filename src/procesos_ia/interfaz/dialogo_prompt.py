"""Diálogo para gestión, creación y refinamiento de prompts asistido por Ollama."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
from procesos_ia.dominio.prompts import PeticionRefinamiento, PlantillaPrompt, ResultadoRefinamiento
from procesos_ia.dominio.evaluaciones import resultados_compatibles, resultados_desde_datos
from procesos_ia.interfaz.borradores import GestorBorradores, volcar_datos_editor
from procesos_ia.interfaz.componentes.barra_navegacion import BarraNavegacionSubvista
from procesos_ia.interfaz.componentes.editor_resultados import EditorResultados
from procesos_ia.interfaz.hilos_evaluacion import HiloRefinamiento
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido
from procesos_ia.interfaz.responsivo import ModoPantalla
from procesos_ia.infraestructura.prompts.parametros import cargar_parametros_evaluacion


class DialogoGestionPrompts(QWidget):
    """Interfaz para administrar y refinar plantillas de prompts integrada en la ventana."""

    plantilla_seleccionada = Signal(PlantillaPrompt)
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
        from procesos_ia.aplicacion.prompts_ia_web import asegurar_plantillas_ia_web
        asegurar_plantillas_ia_web(self._servicio)
        self._modelo_activo = modelo_activo
        self._plantilla_actual: PlantillaPrompt | None = None
        self._iniciar_ui()
        self._cargar_lista()

    def _iniciar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.barra_nav = BarraNavegacionSubvista("Catálogo y Refinador de Prompts", "Limpiar borrador", self)
        self.barra_nav.volver_solicitado.connect(self._al_volver)
        self.barra_nav.limpiar_solicitado.connect(self.limpiar_borrador)
        layout.addWidget(self.barra_nav)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        panel_izq = QWidget(self)
        layout_izq = QVBoxLayout(panel_izq)
        layout_izq.setContentsMargins(0, 0, 0, 12)
        self.combo_filtro = QComboBox(self)
        self.combo_filtro.addItem("Todas las categorías", "")
        self.combo_filtro.addItem("IA Web (DeepSeek, Gemini, Modo IA)", "ia_web")
        self.combo_filtro.currentIndexChanged.connect(self._cargar_lista)
        layout_izq.addWidget(self.combo_filtro)
        self.lista_prompts = QListWidget(self)
        self.lista_prompts.currentRowChanged.connect(self._seleccionar_plantilla)
        layout_izq.addWidget(self.lista_prompts)

        layout_btns_lista = QHBoxLayout()
        self.btn_nuevo = QPushButton("Nuevo", self)
        conectar_boton_protegido(self.btn_nuevo, self._crear_nuevo, "[INFO] Creando nuevo borrador...", self._notificar_estado, 500)
        self.btn_eliminar = QPushButton("Eliminar", self)
        conectar_boton_protegido(self.btn_eliminar, self._eliminar_actual, "[INFO] Eliminando plantilla...", self._notificar_estado, 500)
        layout_btns_lista.addWidget(self.btn_nuevo)
        layout_btns_lista.addWidget(self.btn_eliminar)
        layout_izq.addLayout(layout_btns_lista)
        self.splitter.addWidget(panel_izq)

        panel_der = QWidget(self)
        layout_der = QVBoxLayout(panel_der)
        layout_der.setContentsMargins(0, 0, 0, 12)
        form = QFormLayout()
        self.input_titulo, self.input_categoria = QLineEdit(self), QLineEdit("general", self)
        self.input_descripcion = QLineEdit(self)
        form.addRow("Título:", self.input_titulo)
        form.addRow("Categoría:", self.input_categoria)
        form.addRow("Descripción:", self.input_descripcion)
        layout_der.addLayout(form)

        etiqueta_criterios = QLabel(self._textos["contenido_plantilla"], self)
        etiqueta_criterios.setWordWrap(True)
        layout_der.addWidget(etiqueta_criterios)
        self.texto_contenido = QPlainTextEdit(self)
        self.texto_contenido.setPlaceholderText(self._textos["ejemplo_idea"])
        layout_der.addWidget(self.texto_contenido, stretch=1)
        from procesos_ia.interfaz.componentes.tirador_ajustable import TiradorRedimensionVertical
        self.tirador_prompt = TiradorRedimensionVertical(self.texto_contenido, 100, 450, parent=self)
        layout_der.addWidget(self.tirador_prompt)
        self.editor_resultados = EditorResultados(self); layout_der.addWidget(self.editor_resultados, stretch=1)
        self.estado_refinamiento = QLabel(self)
        self.estado_refinamiento.setWordWrap(True)
        self.estado_refinamiento.setObjectName("estado_refinamiento")
        layout_der.addWidget(self.estado_refinamiento)

        layout_acciones = QHBoxLayout()
        self.btn_refinar = QPushButton("Refinar con IA...", self)
        self.btn_refinar.setToolTip("Optimiza el prompt usando el modelo local")
        conectar_boton_protegido(self.btn_refinar, self._refinar_con_ia, "[INFO] Refinando prompt con IA...", self._notificar_estado, 1000)
        self.btn_guardar = QPushButton("Guardar", self)
        self.btn_guardar.setObjectName("btn_principal")
        conectar_boton_protegido(self.btn_guardar, lambda: self._guardar_actual(), "[INFO] Guardando plantilla...", self._notificar_estado, 600)
        self.btn_usar = QPushButton("Usar en Trabajo", self)
        conectar_boton_protegido(self.btn_usar, self._usar_plantilla, "[INFO] Aplicando plantilla al trabajo...", self._notificar_estado, 600)
        for b in (self.btn_nuevo, self.btn_eliminar, self.btn_refinar, self.btn_guardar, self.btn_usar):
            b.setMinimumHeight(32)
        self.btn_delimitador = QPushButton("Insertar '|'", self)
        self.btn_delimitador.clicked.connect(self._insertar_delimitador)
        for w in (self.btn_refinar, self.btn_delimitador): layout_acciones.addWidget(w)
        layout_acciones.addStretch()
        for w in (self.btn_guardar, self.btn_usar): layout_acciones.addWidget(w)
        layout_der.addLayout(layout_acciones)

        self.splitter.addWidget(panel_der)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        layout.addWidget(self.splitter)

    def _cargar_lista(self, identificador: str | None = None) -> None:
        plantillas = self._servicio.listar_plantillas(categoria=self.combo_filtro.currentData() or None)
        self.lista_prompts.clear()
        for p in plantillas:
            self.lista_prompts.addItem(f"{p.titulo} [{p.categoria}]")
        if plantillas:
            fila = next((i for i, p in enumerate(plantillas) if p.identificador == identificador), 0)
            self.lista_prompts.setCurrentRow(fila)

    def _seleccionar_plantilla(self, fila: int) -> None:
        plantillas = self._servicio.listar_plantillas(categoria=self.combo_filtro.currentData() or None)
        if 0 <= fila < len(plantillas):
            p = plantillas[fila]
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
        from procesos_ia.aplicacion.prompts_ia_web import AYUDA_DELIMITADOR_COLUMNAS
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
            self._cargar_lista(guardada.identificador)
            if mostrar_aviso:
                QMessageBox.information(self, "Guardado", f"[OK] Plantilla '{titulo}' guardada exitosamente.")
            return guardada
        except Exception as error:
            QMessageBox.critical(self, "Error", f"[ERROR] No se pudo guardar: {error}")
            return None

    def _eliminar_actual(self) -> None:
        if not self._plantilla_actual:
            return
        if QMessageBox.question(
            self, "Confirmar eliminación", f"¿Desea eliminar la plantilla '{self._plantilla_actual.titulo}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self._servicio.eliminar_plantilla(self._plantilla_actual.identificador)
            self._crear_nuevo()
            self._cargar_lista()

    def _cambiar_estado_controles(self, habilitado: bool) -> None:
        for w in (self.btn_refinar, self.btn_guardar, self.btn_usar, self.btn_nuevo,
                  self.btn_eliminar, self.combo_filtro, self.lista_prompts, self.editor_resultados):
            w.setEnabled(habilitado)
        self.texto_contenido.setReadOnly(not habilitado)
        self.setCursor(Qt.CursorShape.ArrowCursor if habilitado else Qt.CursorShape.WaitCursor)

    def _refinar_con_ia(self) -> None:
        if self._hilo_refinamiento is not None:
            return
        if not self._modelo_activo:
            self.estado_refinamiento.setText(self._textos.get("modelo_requerido", "[ALERTA] Sin modelo"))
            return
        idea = self.texto_contenido.toPlainText().strip()
        if not idea:
            aviso = self._textos.get("idea_requerida", "[ALERTA] Ingrese una idea")
            self.estado_refinamiento.setText(aviso)
            return
        msg = self._textos.get("refinamiento_en_proceso", "[EN PROCESO] Consultando modelo '{modelo}'...")
        self.estado_refinamiento.setText(msg.format(modelo=self._modelo_activo))
        self._cambiar_estado_controles(False)
        h = HiloRefinamiento(self._servicio, PeticionRefinamiento(idea_usuario=idea), self._modelo_activo, self)
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
        self._plantilla_actual = next((p for p in self._servicio.listar_plantillas()
                                      if p.identificador == identificador), None)
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
            self.plantilla_seleccionada.emit(plantilla)
            self.volver_solicitado.emit()

    def _notificar_estado(self, msj: str) -> None:
        if hasattr(self, "estado_refinamiento") and self.estado_refinamiento:
            self.estado_refinamiento.setText(msj)

    def exec(self) -> int: return 1
    def reject(self) -> None: self._al_volver()
    def accept(self) -> None: self.volver_solicitado.emit()
    def adaptar_modo(self, modo: ModoPantalla) -> None:
        self.splitter.setOrientation(Qt.Orientation.Vertical if modo == ModoPantalla.COMPACTO else Qt.Orientation.Horizontal)
