"""Panel para selección de modelo local, plantilla de prompt e hiperparámetros."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from procesos_ia.dominio.prompts import PlantillaPrompt
from procesos_ia.infraestructura.ollama.modelos import InformacionModelo


class PanelConfiguracionIA(QGroupBox):
    """Configuración de inferencia: modelo Ollama, prompt y parámetros de contexto."""

    solicitar_gestion_prompts = Signal()
    configuracion_cambiada = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("2. Configuración de Inferencia y Modelo", parent)
        self._modelos_disponibles: list[InformacionModelo] = []
        self._plantillas_disponibles: list[PlantillaPrompt] = []

        self._iniciar_ui()

    def _iniciar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 1. Selector de modelo Ollama
        layout_modelo = QHBoxLayout()
        self.label_modelo = QLabel("Modelo Ollama:", self)
        layout_modelo.addWidget(self.label_modelo)

        self.combo_modelos = QComboBox(self)
        self.combo_modelos.setPlaceholderText("Seleccione un modelo instalado...")
        self.combo_modelos.currentIndexChanged.connect(lambda _: self.configuracion_cambiada.emit())
        layout_modelo.addWidget(self.combo_modelos, stretch=1)
        layout.addLayout(layout_modelo)

        # 2. Selector de prompt y boton para abrir catalogo
        layout_prompt = QHBoxLayout()
        self.label_prompt = QLabel("Prompt / Instrucción:", self)
        layout_prompt.addWidget(self.label_prompt)

        self.combo_prompts = QComboBox(self)
        self.combo_prompts.setPlaceholderText("Seleccione o cree una plantilla...")
        self.combo_prompts.currentIndexChanged.connect(lambda _: self.configuracion_cambiada.emit())
        layout_prompt.addWidget(self.combo_prompts, stretch=1)

        self.btn_catalogo_prompts = QPushButton("Catálogo...", self)
        self.btn_catalogo_prompts.setToolTip("Abrir el gestor y refinador de prompts (.md)")
        self.btn_catalogo_prompts.clicked.connect(self.solicitar_gestion_prompts.emit)
        layout_prompt.addWidget(self.btn_catalogo_prompts)
        layout.addLayout(layout_prompt)

        # 3. Hiperparametros en grilla
        layout_params = QGridLayout()
        layout_params.setHorizontalSpacing(14)
        layout_params.setVerticalSpacing(8)

        # Tamano de lote
        layout_params.addWidget(QLabel("Tamaño de lote:", self), 0, 0)
        self.spin_lote = QSpinBox(self)
        self.spin_lote.setRange(1, 100)
        self.spin_lote.setValue(5)
        layout_params.addWidget(self.spin_lote, 0, 1)

        # Temperatura
        layout_params.addWidget(QLabel("Temperatura:", self), 0, 2)
        self.spin_temp = QDoubleSpinBox(self)
        self.spin_temp.setRange(0.0, 1.0)
        self.spin_temp.setSingleStep(0.05)
        self.spin_temp.setValue(0.1)
        layout_params.addWidget(self.spin_temp, 0, 3)

        # Ventana de contexto (num_ctx)
        layout_params.addWidget(QLabel("Ventana contexto:", self), 1, 0)
        self.spin_ctx = QSpinBox(self)
        self.spin_ctx.setRange(512, 32768)
        self.spin_ctx.setSingleStep(512)
        self.spin_ctx.setValue(2048)
        layout_params.addWidget(self.spin_ctx, 1, 1)

        # Particion maxima de salida (filas)
        layout_params.addWidget(QLabel("Límite partición:", self), 1, 2)
        self.spin_particion = QSpinBox(self)
        self.spin_particion.setRange(1000, 2000000)
        self.spin_particion.setSingleStep(50000)
        self.spin_particion.setValue(1000000)
        layout_params.addWidget(self.spin_particion, 1, 3)

        layout.addLayout(layout_params)

    def actualizar_modelos(self, modelos: list[InformacionModelo]) -> None:
        """Puebla la lista desplegable de modelos con sus tamaños en GB."""
        self._modelos_disponibles = list(modelos)
        modelo_actual = self.combo_modelos.currentText().split(" ")[0]
        self.combo_modelos.clear()

        for m in self._modelos_disponibles:
            texto = f"{m.nombre} ({m.tamano_gb} GB, {m.parametros})"
            self.combo_modelos.addItem(texto, m.nombre)

        # Restaurar seleccion si aun existe
        indice = self.combo_modelos.findData(modelo_actual)
        if indice >= 0:
            self.combo_modelos.setCurrentIndex(indice)

    def actualizar_prompts(self, plantillas: list[PlantillaPrompt]) -> None:
        """Puebla la lista de plantillas disponibles del catálogo."""
        self._plantillas_disponibles = list(plantillas)
        self.combo_prompts.clear()

        for p in self._plantillas_disponibles:
            self.combo_prompts.addItem(f"{p.titulo} [{p.categoria}]", p.identificador)

    @property
    def modelo_seleccionado(self) -> str:
        data = self.combo_modelos.currentData()
        if data:
            return str(data)
        return self.combo_modelos.currentText().split(" ")[0]

    @property
    def prompt_sistema_seleccionado(self) -> str:
        id_sel = self.combo_prompts.currentData()
        for p in self._plantillas_disponibles:
            if p.identificador == id_sel:
                return p.contenido
        return "Clasifica y enriquece los datos del registro en formato estructurado JSON."

    @property
    def tamano_lote(self) -> int:
        return self.spin_lote.value()

    @property
    def temperatura(self) -> float:
        return self.spin_temp.value()

    @property
    def ventana_contexto(self) -> int:
        return self.spin_ctx.value()

    @property
    def limite_particion(self) -> int:
        return self.spin_particion.value()
