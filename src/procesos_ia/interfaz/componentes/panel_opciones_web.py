"""Componente con opciones avanzadas de ventana, sesion y tiempos para IA Web."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from procesos_ia.infraestructura.web.configuracion_web import (
    ConfiguracionVentanaWeb,
    ConfiguracionWeb,
)


class PanelOpcionesAvanzadasWeb(QWidget):
    """Panel de opciones secundarias (dimensiones de ventana, sesion y tiempos)."""

    abrir_navegador_solicitado = Signal()
    limpiar_bloqueos_solicitado = Signal()
    aplicar_solicitado = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._iniciar_ui()

    def _iniciar_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        # 1. Grupo de parametros del navegador
        self.grupo_ventana = QGroupBox("Opciones Avanzadas del Navegador", self)
        layout_f = QFormLayout(self.grupo_ventana)
        layout_f.setContentsMargins(10, 10, 10, 10)
        layout_f.setSpacing(8)

        self.check_al_frente = QCheckBox("Mantener ventana de navegador al frente (Always on top)", self)
        self.check_al_frente.setChecked(True)
        layout_f.addRow(self.check_al_frente)

        layout_dim = QHBoxLayout()
        self.spin_ancho = QSpinBox(self)
        self.spin_ancho.setRange(200, 3840); self.spin_ancho.setSuffix(" px"); self.spin_ancho.setMinimumHeight(28)
        layout_dim.addWidget(QLabel("Ancho:", self)); layout_dim.addWidget(self.spin_ancho)

        self.spin_alto = QSpinBox(self)
        self.spin_alto.setRange(200, 2160); self.spin_alto.setSuffix(" px"); self.spin_alto.setMinimumHeight(28)
        layout_dim.addWidget(QLabel("Alto:", self)); layout_dim.addWidget(self.spin_alto)
        layout_f.addRow("Dimensiones ventana:", layout_dim)

        self.spin_espera = QSpinBox(self)
        self.spin_espera.setRange(5, 300); self.spin_espera.setSuffix(" s"); self.spin_espera.setMinimumHeight(28)
        layout_f.addRow("Tiempo límite de respuesta:", self.spin_espera)
        lay.addWidget(self.grupo_ventana)

        # 2. Modo de ejecucion
        layout_m = QHBoxLayout()
        layout_m.addWidget(QLabel("Modo de ejecución:", self))
        self.combo_modo = QComboBox(self)
        self.combo_modo.addItem("Por lotes", "lote"); self.combo_modo.addItem("Registro individual (celda por imagen)", "individual")
        layout_m.addWidget(self.combo_modo, stretch=1)
        lay.addLayout(layout_m)

        # 3. Acciones de sesion
        grupo_sesion = QGroupBox("Acciones de Sesión del Navegador", self)
        lay_s = QHBoxLayout(grupo_sesion)
        self.btn_abrir_navegador = QPushButton("Abrir Navegador (Login / Verificación)", self)
        self.btn_abrir_navegador.setMinimumHeight(32)
        self.btn_abrir_navegador.clicked.connect(self.abrir_navegador_solicitado.emit); lay_s.addWidget(self.btn_abrir_navegador)
        self.btn_limpiar_bloqueos = QPushButton("Limpiar Bloqueos (SingletonLock)", self)
        self.btn_limpiar_bloqueos.setMinimumHeight(32)
        self.btn_limpiar_bloqueos.clicked.connect(self.limpiar_bloqueos_solicitado.emit); lay_s.addWidget(self.btn_limpiar_bloqueos)
        lay.addWidget(grupo_sesion)

        # 4. Boton guardar
        self.btn_aplicar = QPushButton("Guardar Configuración y Volver", self)
        self.btn_aplicar.setMinimumHeight(34)
        self.btn_aplicar.clicked.connect(self.aplicar_solicitado.emit); lay.addWidget(self.btn_aplicar)
        lay.addStretch()

    def sincronizar_desde_config(self, cfg: ConfiguracionWeb) -> None:
        self.check_al_frente.setChecked(cfg.ventana.siempre_al_frente)
        self.spin_ancho.setValue(cfg.ventana.ancho)
        self.spin_alto.setValue(cfg.ventana.alto)
        self.spin_espera.setValue(cfg.tiempo_espera_respuesta_segundos)

    def obtener_ventana_web(self) -> ConfiguracionVentanaWeb:
        return ConfiguracionVentanaWeb(
            ancho=self.spin_ancho.value(),
            alto=self.spin_alto.value(),
            siempre_al_frente=self.check_al_frente.isChecked(),
        )

    def tiempo_espera(self) -> int:
        return self.spin_espera.value()
