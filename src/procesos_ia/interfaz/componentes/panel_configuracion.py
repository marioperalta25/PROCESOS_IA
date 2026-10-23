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
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from procesos_ia.dominio.prompts import PlantillaPrompt
from procesos_ia.dominio.evaluaciones import resultados_compatibles
from procesos_ia.infraestructura.prompts.parametros import cargar_parametros_evaluacion
from procesos_ia.infraestructura.ollama.modelos import InformacionModelo
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido
from procesos_ia.interfaz.responsivo import ModoPantalla


class PanelConfiguracionIA(QGroupBox):
    """Configuración de inferencia: modelo Ollama, prompt y parámetros de contexto."""

    solicitar_gestion_prompts = Signal()
    solicitar_actualizacion_modelos = Signal()
    configuracion_cambiada = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("2. Configuración de Inferencia y Modelo (Ollama Local)", parent)
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

        self.btn_refrescar_modelos = QPushButton("Actualizar", self)
        self.btn_refrescar_modelos.setToolTip("Consultar modelos e iniciar Ollama local si la conexion es rechazada")
        conectar_boton_protegido(
            self.btn_refrescar_modelos, self.solicitar_actualizacion_modelos.emit,
            "[INFO] Consultando modelos instalados en Ollama...", tiempo_bloqueo_ms=1000,
        )
        layout_modelo.addWidget(self.btn_refrescar_modelos)
        layout.addLayout(layout_modelo)

        # 2. Selector de prompt y boton para abrir catalogo
        layout_prompt = QHBoxLayout()
        self.label_prompt = QLabel("Prompt / Instrucción:", self)
        layout_prompt.addWidget(self.label_prompt)

        self.combo_prompts = QComboBox(self)
        self.combo_prompts.setPlaceholderText("Seleccione o cree una plantilla...")
        self.combo_prompts.currentIndexChanged.connect(self._al_cambiar_prompt)
        layout_prompt.addWidget(self.combo_prompts, stretch=1)

        self.btn_catalogo_prompts = QPushButton("Catálogo...", self)
        self.btn_catalogo_prompts.setToolTip("Abrir el gestor y refinador de prompts (.md)")
        conectar_boton_protegido(
            self.btn_catalogo_prompts, self.solicitar_gestion_prompts.emit,
            "[INFO] Accediendo al catálogo de plantillas de prompts...", tiempo_bloqueo_ms=800,
        )
        layout_prompt.addWidget(self.btn_catalogo_prompts)
        layout.addLayout(layout_prompt)

        # 3. Columnas de salida esperadas
        layout_salida = QHBoxLayout()
        self.label_salida = QLabel(cargar_parametros_evaluacion()["resultados_plantilla"], self)
        layout_salida.addWidget(self.label_salida)

        self.input_columnas_salida = QLineEdit(self)
        self.input_columnas_salida.setReadOnly(True)
        self.input_columnas_salida.textChanged.connect(lambda _: self.configuracion_cambiada.emit())
        layout_salida.addWidget(self.input_columnas_salida, stretch=1)
        layout.addLayout(layout_salida)

        # 4. Hiperparametros en grilla
        self.layout_params = QGridLayout()
        self.layout_params.setHorizontalSpacing(14)
        self.layout_params.setVerticalSpacing(8)

        self.lbl_lote = QLabel("Tamaño de lote:", self)
        self.spin_lote = QSpinBox(self)
        self.spin_lote.setRange(1, 100)
        self.spin_lote.setValue(5)

        self.lbl_temp = QLabel("Temperatura:", self)
        self.spin_temp = QDoubleSpinBox(self)
        self.spin_temp.setRange(0.0, 1.0)
        self.spin_temp.setSingleStep(0.05)
        self.spin_temp.setValue(0.1)

        self.lbl_ctx = QLabel("Ventana contexto:", self)
        self.spin_ctx = QSpinBox(self)
        self.spin_ctx.setRange(512, 32768)
        self.spin_ctx.setSingleStep(512)
        self.spin_ctx.setValue(2048)

        self.lbl_particion = QLabel("Límite partición:", self)
        self.spin_particion = QSpinBox(self)
        self.spin_particion.setRange(1000, 2000000)
        self.spin_particion.setSingleStep(50000)
        self.spin_particion.setValue(1000000)

        self.lbl_tiempo = QLabel("Tiempo límite lote (s):", self)
        self.spin_tiempo_limite = QSpinBox(self)
        self.spin_tiempo_limite.setRange(5, 600)
        self.spin_tiempo_limite.setValue(60)

        self.adaptar_modo(ModoPantalla.ESTANDAR)
        layout.addLayout(self.layout_params)

    def _al_cambiar_prompt(self) -> None:
        id_sel = self.combo_prompts.currentData()
        columnas = ()
        for p in self._plantillas_disponibles:
            if p.identificador == id_sel:
                columnas = tuple(r.clave for r in resultados_compatibles(p))
                break
        self.input_columnas_salida.setText(", ".join(columnas))
        self.configuracion_cambiada.emit()

    def actualizar_modelos(self, modelos: list[InformacionModelo]) -> None:
        """Puebla la lista desplegable de modelos con sus tamaños en GB."""
        self._modelos_disponibles = list(modelos)
        modelo_actual = self.combo_modelos.currentData() or self.combo_modelos.currentText().split(" ")[0]
        self.combo_modelos.clear()
        for m in self._modelos_disponibles:
            self.combo_modelos.addItem(f"{m.nombre} ({m.tamano_gb} GB, {m.parametros})", m.nombre)
        if self._modelos_disponibles:
            indice = self.combo_modelos.findData(modelo_actual)
            self.combo_modelos.setCurrentIndex(indice if indice >= 0 else 0)

    def actualizar_prompts(self, plantillas: list[PlantillaPrompt]) -> None:
        """Puebla la lista de plantillas disponibles conservando la selección previa."""
        prompt_actual = self.combo_prompts.currentData()
        self._plantillas_disponibles = list(plantillas)
        self.combo_prompts.clear()
        for p in self._plantillas_disponibles:
            self.combo_prompts.addItem(f"{p.titulo} [{p.categoria}]", p.identificador)
        if self._plantillas_disponibles:
            indice = self.combo_prompts.findData(prompt_actual)
            self.combo_prompts.setCurrentIndex(indice if indice >= 0 else 0)
            self._al_cambiar_prompt()

    @property
    def plantilla_seleccionada(self) -> PlantillaPrompt | None:
        return next((p for p in self._plantillas_disponibles
                     if p.identificador == self.combo_prompts.currentData()), None)

    @property
    def modelo_seleccionado(self) -> str:
        data = self.combo_modelos.currentData()
        return str(data) if data else self.combo_modelos.currentText().split(" ")[0]

    @property
    def prompt_sistema_seleccionado(self) -> str:
        id_sel = self.combo_prompts.currentData()
        for p in self._plantillas_disponibles:
            if p.identificador == id_sel:
                return p.contenido
        return "Clasifica y enriquece los datos del registro en formato estructurado JSON."

    @property
    def columnas_salida_modelo(self) -> tuple[str, ...]:
        texto = self.input_columnas_salida.text().strip()
        return tuple(col.strip() for col in texto.split(",") if col.strip()) if texto else ()

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

    @property
    def tiempo_limite_lote_segundos(self) -> float:
        return float(self.spin_tiempo_limite.value())

    def adaptar_modo(self, modo: ModoPantalla) -> None:
        """Adapta la grilla de hiperparametros entre 1 columna de pares o 2."""
        for w in (self.lbl_lote, self.spin_lote, self.lbl_temp, self.spin_temp,
                  self.lbl_ctx, self.spin_ctx, self.lbl_particion, self.spin_particion,
                  self.lbl_tiempo, self.spin_tiempo_limite):
            self.layout_params.removeWidget(w)
        if modo == ModoPantalla.COMPACTO:
            pares = ((self.lbl_lote, self.spin_lote), (self.lbl_temp, self.spin_temp),
                     (self.lbl_ctx, self.spin_ctx), (self.lbl_particion, self.spin_particion),
                     (self.lbl_tiempo, self.spin_tiempo_limite))
            for f, (l, c) in enumerate(pares):
                self.layout_params.addWidget(l, f, 0)
                self.layout_params.addWidget(c, f, 1)
        else:
            grid = ((self.lbl_lote, self.spin_lote, self.lbl_temp, self.spin_temp),
                    (self.lbl_ctx, self.spin_ctx, self.lbl_particion, self.spin_particion),
                    (self.lbl_tiempo, self.spin_tiempo_limite, None, None))
            for f, row in enumerate(grid):
                for c, w in enumerate(row):
                    if w:
                        self.layout_params.addWidget(w, f, c)
