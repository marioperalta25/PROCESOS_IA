"""Composicion visual e interfaz de usuario para el catalogo y refinador de prompts."""

from __future__ import annotations

from typing import TYPE_CHECKING
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from procesos_ia.interfaz.componentes.barra_navegacion import BarraNavegacionSubvista
from procesos_ia.interfaz.componentes.editor_resultados import EditorResultados
from procesos_ia.interfaz.componentes.tirador_ajustable import TiradorRedimensionVertical
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido

if TYPE_CHECKING:
    from procesos_ia.interfaz.dialogo_prompt import DialogoGestionPrompts


def construir_interfaz_prompts(dialogo: DialogoGestionPrompts) -> None:
    """Ensambla todos los paneles, widgets y controles visuales del dialogo de prompts."""
    layout = QVBoxLayout(dialogo)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(8)

    dialogo.barra_nav = BarraNavegacionSubvista("Catálogo y Refinador de Prompts", "Limpiar borrador", dialogo)
    dialogo.barra_nav.volver_solicitado.connect(dialogo._al_volver)
    dialogo.barra_nav.limpiar_solicitado.connect(dialogo.limpiar_borrador)
    layout.addWidget(dialogo.barra_nav, 0)

    dialogo.splitter = QSplitter(Qt.Orientation.Horizontal, dialogo)

    # 1. Panel Izquierdo: Lista y Categorias
    panel_izq = QWidget(dialogo)
    layout_izq = QVBoxLayout(panel_izq)
    layout_izq.setContentsMargins(0, 0, 0, 12)

    lbl_lista = QLabel("Plantillas del Catálogo:", dialogo)
    lbl_lista.setStyleSheet("font-weight: bold;")
    layout_izq.addWidget(lbl_lista)

    lbl_ayuda_lista = QLabel("[INFO] Filtra por categoría y selecciona una plantilla para editarla o usarla.", dialogo)
    lbl_ayuda_lista.setWordWrap(True)
    lbl_ayuda_lista.setStyleSheet("color: #58615B; font-size: 11px;")
    layout_izq.addWidget(lbl_ayuda_lista)

    dialogo.combo_filtro = QComboBox(dialogo)
    dialogo.combo_filtro.addItem("Todas las categorías", "")
    dialogo.combo_filtro.addItem("IA Web (DeepSeek, Gemini, Modo IA)", "ia_web")
    dialogo.combo_filtro.currentIndexChanged.connect(dialogo._cargar_lista)
    layout_izq.addWidget(dialogo.combo_filtro)

    dialogo.lista_prompts = QListWidget(dialogo)
    dialogo.lista_prompts.currentRowChanged.connect(dialogo._seleccionar_plantilla)
    layout_izq.addWidget(dialogo.lista_prompts)

    layout_btns_lista = QHBoxLayout()
    dialogo.btn_nuevo = QPushButton("Nuevo", dialogo)
    dialogo.btn_eliminar = QPushButton("Eliminar", dialogo)
    conectar_boton_protegido(dialogo.btn_nuevo, dialogo._crear_nuevo, "[INFO] Creando nuevo borrador...", dialogo._notificar_estado, 500)
    conectar_boton_protegido(dialogo.btn_eliminar, dialogo._eliminar_actual, "[INFO] Eliminando...", dialogo._notificar_estado, 500)
    layout_btns_lista.addWidget(dialogo.btn_nuevo)
    layout_btns_lista.addWidget(dialogo.btn_eliminar)
    layout_izq.addLayout(layout_btns_lista)
    dialogo.splitter.addWidget(panel_izq)

    # 2. Panel Derecho: Formulario y Editor dentro de QScrollArea para evitar solapamientos
    dialogo.scroll_der = QScrollArea(dialogo.splitter)
    dialogo.scroll_der.setWidgetResizable(True)
    dialogo.scroll_der.setFrameShape(QScrollArea.Shape.NoFrame)
    dialogo.scroll_der.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    dialogo.scroll_der.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    panel_der = QWidget()
    dialogo.scroll_der.setWidget(panel_der)
    layout_der = QVBoxLayout(panel_der)
    layout_der.setContentsMargins(6, 0, 10, 12)
    layout_der.setSpacing(8)

    lbl_meta = QLabel("Metadatos de la Plantilla:", dialogo)
    lbl_meta.setStyleSheet("font-weight: bold;")
    layout_der.addWidget(lbl_meta)

    form = QFormLayout()
    dialogo.input_titulo = QLineEdit(dialogo)
    dialogo.input_categoria = QLineEdit("general", dialogo)
    dialogo.input_descripcion = QLineEdit(dialogo)
    form.addRow("Título:", dialogo.input_titulo)
    form.addRow("Categoría:", dialogo.input_categoria)
    form.addRow("Descripción:", dialogo.input_descripcion)
    layout_der.addLayout(form)

    etiqueta_criterios = QLabel(
        "Instrucciones del Prompt:\n"
        "Escribe la tarea para la IA (ej. clasificar registros, comparar columnas o extraer datos). "
        "Usa texto libre o reglas delimitadas con '|'.",
        dialogo,
    )
    etiqueta_criterios.setWordWrap(True)
    etiqueta_criterios.setStyleSheet("font-weight: bold; margin-top: 4px;")
    layout_der.addWidget(etiqueta_criterios)

    dialogo.texto_contenido = QPlainTextEdit(panel_der)
    dialogo.texto_contenido.setPlaceholderText(dialogo._textos["ejemplo_idea"])
    dialogo.texto_contenido.setMinimumHeight(120)
    dialogo.texto_contenido.setFixedHeight(160)
    layout_der.addWidget(dialogo.texto_contenido)

    dialogo.tirador_prompt = TiradorRedimensionVertical(
        dialogo.texto_contenido, 100, 550, parent=panel_der,
    )
    layout_der.addWidget(dialogo.tirador_prompt)

    dialogo.editor_resultados = EditorResultados(panel_der)
    layout_der.addWidget(dialogo.editor_resultados)

    dialogo.estado_refinamiento = QLabel(panel_der)
    dialogo.estado_refinamiento.setWordWrap(True)
    dialogo.estado_refinamiento.setObjectName("estado_refinamiento")
    layout_der.addWidget(dialogo.estado_refinamiento)

    # 3. Fila de refinacion con selector de modelo Ollama
    layout_refinar = QHBoxLayout()
    layout_refinar.addWidget(QLabel("Modelo Ollama:", dialogo))
    dialogo.combo_modelos = QComboBox(dialogo)
    dialogo.combo_modelos.setMinimumHeight(28)
    dialogo.combo_modelos.currentTextChanged.connect(dialogo._al_cambiar_modelo)
    layout_refinar.addWidget(dialogo.combo_modelos, stretch=1)

    dialogo.btn_refinar = QPushButton("Refinar con IA...", dialogo)
    dialogo.btn_refinar.setMinimumHeight(28)
    dialogo.btn_refinar.setToolTip("Optimiza el prompt usando el modelo local seleccionado en Ollama")
    conectar_boton_protegido(dialogo.btn_refinar, dialogo._refinar_con_ia, "[INFO] Refinando...", dialogo._notificar_estado, 1000)
    layout_refinar.addWidget(dialogo.btn_refinar)

    dialogo.btn_delimitador = QPushButton("Insertar '|'", dialogo)
    dialogo.btn_delimitador.setMinimumHeight(28)
    conectar_boton_protegido(
        dialogo.btn_delimitador,
        dialogo._insertar_delimitador,
        "[INFO] Insertando delimitador '|'...",
        dialogo._notificar_estado,
        300,
    )
    layout_refinar.addWidget(dialogo.btn_delimitador)
    layout_der.addLayout(layout_refinar)

    # 4. Fila de guardado y aplicacion
    layout_guardar = QHBoxLayout()
    layout_guardar.addStretch()
    dialogo.btn_guardar = QPushButton("Guardar", dialogo)
    dialogo.btn_guardar.setObjectName("btn_principal")
    dialogo.btn_guardar.setMinimumHeight(32)
    conectar_boton_protegido(dialogo.btn_guardar, lambda: dialogo._guardar_actual(), "[INFO] Guardando...", dialogo._notificar_estado, 600)

    dialogo.btn_usar = QPushButton("Usar en Trabajo", dialogo)
    dialogo.btn_usar.setMinimumHeight(32)
    conectar_boton_protegido(dialogo.btn_usar, dialogo._usar_plantilla, "[INFO] Aplicando...", dialogo._notificar_estado, 600)
    layout_guardar.addWidget(dialogo.btn_guardar)
    layout_guardar.addWidget(dialogo.btn_usar)
    layout_der.addLayout(layout_guardar)

    dialogo.splitter.addWidget(dialogo.scroll_der)
    dialogo.splitter.setStretchFactor(0, 1)
    dialogo.splitter.setStretchFactor(1, 3)
    layout.addWidget(dialogo.splitter, stretch=1)
