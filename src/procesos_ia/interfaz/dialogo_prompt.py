"""Diálogo para gestión, creación y refinamiento de prompts asistido por Ollama."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
from procesos_ia.dominio.prompts import PeticionRefinamiento, PlantillaPrompt


class DialogoGestionPrompts(QDialog):
    """Interfaz modal para administrar y refinar plantillas de prompts en Markdown."""

    plantilla_seleccionada = Signal(PlantillaPrompt)

    def __init__(
        self,
        servicio_prompts: ServicioCatalogoPrompts,
        modelo_activo: str = "qwen2.5:1.5b",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Catálogo y Refinador de Prompts")
        self.resize(750, 520)

        self._servicio = servicio_prompts
        self._modelo_activo = modelo_activo
        self._plantilla_actual: PlantillaPrompt | None = None

        self._iniciar_ui()
        self._cargar_lista()

    def _iniciar_ui(self) -> None:
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # 1. Panel izquierdo: lista de plantillas y categorias
        panel_izq = QWidget(self)
        layout_izq = QVBoxLayout(panel_izq)
        layout_izq.setContentsMargins(0, 0, 0, 0)

        self.combo_filtro = QComboBox(self)
        self.combo_filtro.addItem("Todas las categorías", "")
        self.combo_filtro.currentIndexChanged.connect(self._cargar_lista)
        layout_izq.addWidget(self.combo_filtro)

        self.lista_prompts = QListWidget(self)
        self.lista_prompts.currentRowChanged.connect(self._seleccionar_plantilla)
        layout_izq.addWidget(self.lista_prompts)

        layout_btns_lista = QHBoxLayout()
        self.btn_nuevo = QPushButton("Nuevo", self)
        self.btn_nuevo.clicked.connect(self._crear_nuevo)
        layout_btns_lista.addWidget(self.btn_nuevo)

        self.btn_eliminar = QPushButton("Eliminar", self)
        self.btn_eliminar.clicked.connect(self._eliminar_actual)
        layout_btns_lista.addWidget(self.btn_eliminar)
        layout_izq.addLayout(layout_btns_lista)

        splitter.addWidget(panel_izq)

        # 2. Panel derecho: editor y refinamiento
        panel_der = QWidget(self)
        layout_der = QVBoxLayout(panel_der)
        layout_der.setContentsMargins(0, 0, 0, 0)

        form = QFormLayout()
        self.input_titulo = QLineEdit(self)
        form.addRow("Título:", self.input_titulo)

        self.input_categoria = QLineEdit("general", self)
        form.addRow("Categoría:", self.input_categoria)

        self.input_descripcion = QLineEdit(self)
        form.addRow("Descripción:", self.input_descripcion)
        layout_der.addLayout(form)

        layout_der.addWidget(QLabel("Contenido del prompt (instrucción del sistema):", self))
        self.texto_contenido = QPlainTextEdit(self)
        layout_der.addWidget(self.texto_contenido, stretch=1)

        layout_acciones = QHBoxLayout()
        self.btn_refinar = QPushButton("Refinar con IA...", self)
        self.btn_refinar.setToolTip("Optimiza el prompt usando el modelo local")
        self.btn_refinar.clicked.connect(self._refinar_con_ia)
        layout_acciones.addWidget(self.btn_refinar)

        layout_acciones.addStretch()

        self.btn_guardar = QPushButton("Guardar", self)
        self.btn_guardar.setObjectName("btn_principal")
        self.btn_guardar.clicked.connect(self._guardar_actual)
        layout_acciones.addWidget(self.btn_guardar)

        self.btn_usar = QPushButton("Usar en Trabajo", self)
        self.btn_usar.clicked.connect(self._usar_plantilla)
        layout_acciones.addWidget(self.btn_usar)

        layout_der.addLayout(layout_acciones)

        splitter.addWidget(panel_der)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

    def _cargar_lista(self) -> None:
        cat = self.combo_filtro.currentData()
        plantillas = self._servicio.listar_plantillas(categoria=cat or None)
        self.lista_prompts.clear()

        for p in plantillas:
            self.lista_prompts.addItem(f"{p.titulo} [{p.categoria}]")

        if plantillas:
            self.lista_prompts.setCurrentRow(0)

    def _seleccionar_plantilla(self, fila: int) -> None:
        cat = self.combo_filtro.currentData()
        plantillas = self._servicio.listar_plantillas(categoria=cat or None)
        if 0 <= fila < len(plantillas):
            p = plantillas[fila]
            self._plantilla_actual = p
            self.input_titulo.setText(p.titulo)
            self.input_categoria.setText(p.categoria)
            self.input_descripcion.setText(p.descripcion)
            self.texto_contenido.setPlainText(p.contenido)

    def _crear_nuevo(self) -> None:
        self._plantilla_actual = None
        self.input_titulo.setText("Nueva Plantilla")
        self.input_categoria.setText("general")
        self.input_descripcion.setText("")
        self.texto_contenido.setPlainText(
            "Eres un evaluador de datos. Clasifica el siguiente texto y responde en JSON."
        )

    def _guardar_actual(self) -> None:
        titulo = self.input_titulo.text().strip()
        contenido = self.texto_contenido.toPlainText().strip()
        categoria = self.input_categoria.text().strip() or "general"
        descripcion = self.input_descripcion.text().strip()

        if not titulo or not contenido:
            QMessageBox.warning(self, "Validación", "[ALERTA] El título y el contenido son obligatorios.")
            return

        id_existente = self._plantilla_actual.identificador if self._plantilla_actual else None

        try:
            guardada = self._servicio.crear_plantilla(
                titulo=titulo,
                contenido=contenido,
                categoria=categoria,
                descripcion=descripcion,
                identificador=id_existente,
            )
            self._plantilla_actual = guardada
            self._cargar_lista()
            QMessageBox.information(self, "Guardado", f"[OK] Plantilla '{titulo}' guardada exitosamente.")
        except Exception as error:
            QMessageBox.critical(self, "Error", f"[ERROR] No se pudo guardar: {error}")

    def _eliminar_actual(self) -> None:
        if not self._plantilla_actual:
            return
        resp = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Desea eliminar la plantilla '{self._plantilla_actual.titulo}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp == QMessageBox.StandardButton.Yes:
            self._servicio.eliminar_plantilla(self._plantilla_actual.identificador)
            self._crear_nuevo()
            self._cargar_lista()

    def _refinar_con_ia(self) -> None:
        peticion = PeticionRefinamiento(
            idea_usuario=self.texto_contenido.toPlainText(),
        )
        try:
            res = self._servicio.refinar_idea(peticion, self._modelo_activo)
            if res.prompt_refinado:
                self.texto_contenido.setPlainText(res.prompt_refinado)
                QMessageBox.information(
                    self, "Refinamiento Completado", f"[OK] Prompt refinado por {self._modelo_activo}"
                )
        except Exception as err:
            QMessageBox.critical(self, "Error", f"[ERROR] Fallo en servicio de refinamiento: {err}")

    def _usar_plantilla(self) -> None:
        if self._plantilla_actual:
            self.plantilla_seleccionada.emit(self._plantilla_actual)
            self.accept()
