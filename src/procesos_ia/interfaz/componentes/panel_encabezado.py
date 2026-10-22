"""Panel de encabezado con identidad visual, emblema y estado de Ollama."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from procesos_ia.infraestructura.ollama.modelos import (
    DiagnosticoOllama,
    EstadoServicioOllama,
)
from procesos_ia.interfaz.recursos import GestorRecursos
from procesos_ia.interfaz.tema import PaletaVisual


class PanelEncabezado(QWidget):
    """Muestra el emblema del dragón, el título del sistema y el estado de Ollama."""

    solicitar_actualizacion_ollama = Signal()

    def __init__(
        self,
        gestor_recursos: GestorRecursos | None = None,
        paleta: PaletaVisual | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._recursos = gestor_recursos or GestorRecursos()
        self._paleta = paleta or PaletaVisual()

        self._iniciar_ui()

    def _iniciar_ui(self) -> None:
        layout_principal = QHBoxLayout(self)
        layout_principal.setContentsMargins(12, 10, 12, 10)
        layout_principal.setSpacing(14)

        # 1. Emblema del dragon
        self.label_emblema = QLabel(self)
        pix = self._recursos.obtener_pixmap_emblema(56, 56)
        if not pix.isNull():
            self.label_emblema.setPixmap(pix)
        self.label_emblema.setFixedSize(56, 56)
        layout_principal.addWidget(self.label_emblema)

        # 2. Titulo y descripcion del sistema
        layout_textos = QVBoxLayout()
        layout_textos.setSpacing(2)

        self.label_titulo = QLabel("PROCESOS_IA", self)
        self.label_titulo.setObjectName("titulo_principal")
        layout_textos.addWidget(self.label_titulo)

        self.label_subtitulo = QLabel(
            "Enriquecimiento Tabular Masivo y Recuperacion WAL con Ollama", self
        )
        self.label_subtitulo.setObjectName("subtitulo")
        layout_textos.addWidget(self.label_subtitulo)

        layout_principal.addLayout(layout_textos, stretch=1)

        # 3. Estado de Ollama y boton de refresco
        layout_estado = QVBoxLayout()
        layout_estado.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout_estado.setSpacing(4)

        self.badge_estado = QLabel("[CONSULTANDO ESTADO]", self)
        self.badge_estado.setObjectName("estado_pill")
        self.badge_estado.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_estado.addWidget(self.badge_estado)

        self.btn_refrescar = QPushButton("Verificar Conexion", self)
        self.btn_refrescar.setToolTip("Comprobar el daemon local de Ollama")
        self.btn_refrescar.clicked.connect(self.solicitar_actualizacion_ollama.emit)
        layout_estado.addWidget(self.btn_refrescar)

        layout_principal.addLayout(layout_estado)

    def actualizar_estado_ollama(self, diagnostico: DiagnosticoOllama) -> None:
        """Actualiza el indicador visual según el diagnóstico de Ollama."""
        estado = diagnostico.estado
        if estado == EstadoServicioOllama.DISPONIBLE:
            v = diagnostico.version_servidor or "activa"
            self.badge_estado.setText(f"[DISPONIBLE - v{v}]")
            self.badge_estado.setStyleSheet(
                f"background-color: #E2ECE8; color: {self._paleta.exito}; "
                f"border: 1px solid {self._paleta.exito}; border-radius: 12px; font-weight: bold;"
            )
        elif estado == EstadoServicioOllama.DETENIDO:
            self.badge_estado.setText("[SERVICIO DETENIDO]")
            self.badge_estado.setStyleSheet(
                f"background-color: #F8F1E5; color: {self._paleta.advertencia}; "
                f"border: 1px solid {self._paleta.advertencia}; border-radius: 12px; font-weight: bold;"
            )
        elif estado == EstadoServicioOllama.NO_INSTALADO:
            self.badge_estado.setText("[NO INSTALADO]")
            self.badge_estado.setStyleSheet(
                f"background-color: #F9EBEB; color: {self._paleta.error}; "
                f"border: 1px solid {self._paleta.error}; border-radius: 12px; font-weight: bold;"
            )
        else:
            self.badge_estado.setText("[ERROR CONEXION]")
            self.badge_estado.setStyleSheet(
                f"background-color: #F9EBEB; color: {self._paleta.error}; "
                f"border: 1px solid {self._paleta.error}; border-radius: 12px; font-weight: bold;"
            )
