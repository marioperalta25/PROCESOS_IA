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
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido
from procesos_ia.interfaz.recursos import GestorRecursos
from procesos_ia.interfaz.responsivo import ModoPantalla
from procesos_ia.interfaz.tema import PaletaVisual


class PanelEncabezado(QWidget):
    """Muestra el emblema del dragón, el título del sistema y el estado de Ollama."""

    solicitar_actualizacion_ollama = Signal()
    solicitar_chat = Signal()
    solicitar_configuracion_motores = Signal()

    def __init__(
        self,
        gestor_recursos: GestorRecursos | None = None,
        paleta: PaletaVisual | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._recursos = gestor_recursos or GestorRecursos()
        self._paleta = paleta or PaletaVisual()
        self._modo_actual = ModoPantalla.ESTANDAR
        self._motor_activo = "ollama"

        self._iniciar_ui()

    def _iniciar_ui(self) -> None:
        self.setObjectName("panel_encabezado_tarjeta")
        self.setStyleSheet(
            "QWidget#panel_encabezado_tarjeta { "
            "background-color: #FFFCF7; "
            "border: 1px solid #D9D1C5; "
            "border-radius: 8px; "
            "}"
        )

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(14, 12, 14, 12)
        layout_raiz.setSpacing(10)

        # Fila 1: Identidad (Logo, Titulo, Subtitulo) y Badge de estado a la derecha
        fila_superior = QHBoxLayout()
        fila_superior.setSpacing(12)

        self.label_emblema = QLabel(self)
        pix = self._recursos.obtener_pixmap_emblema(52, 52)
        if not pix.isNull():
            self.label_emblema.setPixmap(pix)
        self.label_emblema.setFixedSize(52, 52)
        self.label_emblema.setStyleSheet("border-radius: 6px; background-color: #EDE7DC; padding: 2px;")
        fila_superior.addWidget(self.label_emblema)

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
        fila_superior.addLayout(layout_textos, stretch=1)

        self.badge_estado = QLabel("[CONSULTANDO ESTADO]", self)
        self.badge_estado.setObjectName("estado_pill")
        self.badge_estado.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge_estado.setMinimumHeight(28)
        self.badge_estado.setStyleSheet(
            "background-color: #EDE7DC; color: #58615B; border: 1px solid #D9D1C5; "
            "border-radius: 14px; padding: 4px 14px; font-weight: 600; font-size: 8.5pt;"
        )
        fila_superior.addWidget(self.badge_estado, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        layout_raiz.addLayout(fila_superior)

        # Fila 2: Barra de Acciones Horizontal balanceada y elegante
        self.layout_acciones = QHBoxLayout()
        self.layout_acciones.setSpacing(10)

        self.btn_refrescar = QPushButton("Conectar / Iniciar Ollama", self)
        self.btn_refrescar.setMinimumHeight(32)
        self.btn_refrescar.setToolTip("Consultar modelos e iniciar Ollama local si la conexion es rechazada")
        conectar_boton_protegido(
            self.btn_refrescar,
            self.solicitar_actualizacion_ollama.emit,
            "[INFO] Comprobando servicio e iniciando Ollama...",
            tiempo_bloqueo_ms=1000,
        )
        self.layout_acciones.addWidget(self.btn_refrescar, stretch=1)

        from procesos_ia.infraestructura.ollama.parametros_chat import cargar_parametros_chat
        self.btn_chat = QPushButton(cargar_parametros_chat()["textos"]["abrir"], self)
        self.btn_chat.setMinimumHeight(32)
        conectar_boton_protegido(
            self.btn_chat,
            self.solicitar_chat.emit,
            "[INFO] Abriendo asistente interactivo de chat...",
            tiempo_bloqueo_ms=800,
        )
        self.layout_acciones.addWidget(self.btn_chat, stretch=1)

        self.btn_ia_web = QPushButton("IA Web (DeepSeek / Gemini / Lens)", self)
        self.btn_motores = self.btn_ia_web
        self.btn_ia_web.setMinimumHeight(32)
        self.btn_ia_web.setToolTip("Abrir módulo de inferencia web (DeepSeek / Gemini con imágenes y lotes)")
        conectar_boton_protegido(
            self.btn_ia_web,
            self.solicitar_configuracion_motores.emit,
            "[INFO] Abriendo módulo de IA Web...",
            tiempo_bloqueo_ms=800,
        )
        self.layout_acciones.addWidget(self.btn_ia_web, stretch=1)

        layout_raiz.addLayout(self.layout_acciones)

    def actualizar_motor_activo(self, tipo: str) -> None:
        """Compatibilidad: el botón mantiene su identidad fija para IA Web."""
        pass

    def adaptar_modo(self, modo: ModoPantalla) -> None:
        """Ajusta textos y visibilidad de detalles según el espacio disponible."""
        self._modo_actual = modo
        if modo == ModoPantalla.COMPACTO:
            self.label_subtitulo.setVisible(False)
            self.btn_refrescar.setText("Reconectar")
            self.btn_ia_web.setText("IA Web")
            self.label_emblema.setFixedSize(40, 40)
        else:
            self.label_subtitulo.setVisible(True)
            self.btn_refrescar.setText("Conectar / Iniciar Ollama")
            self.btn_ia_web.setText("IA Web (DeepSeek / Gemini / Lens)")
            self.label_emblema.setFixedSize(52, 52)

    def actualizar_estado_ollama(self, diagnostico: DiagnosticoOllama) -> None:
        """Actualiza el indicador visual según el diagnóstico de Ollama."""
        estado = diagnostico.estado
        if estado == EstadoServicioOllama.DISPONIBLE:
            v = diagnostico.version_servidor or "activa"
            self.badge_estado.setText(f"[DISPONIBLE - v{v}]")
            self.badge_estado.setStyleSheet(
                f"background-color: #E2ECE8; color: {self._paleta.exito}; "
                f"border: 1px solid {self._paleta.exito}; border-radius: 14px; padding: 4px 14px; font-weight: bold;"
            )
        elif estado == EstadoServicioOllama.DETENIDO:
            self.badge_estado.setText("[SERVICIO DETENIDO]")
            self.badge_estado.setStyleSheet(
                f"background-color: #F8F1E5; color: {self._paleta.advertencia}; "
                f"border: 1px solid {self._paleta.advertencia}; border-radius: 14px; padding: 4px 14px; font-weight: bold;"
            )
        elif estado == EstadoServicioOllama.NO_INSTALADO:
            self.badge_estado.setText("[NO INSTALADO]")
            self.badge_estado.setStyleSheet(
                f"background-color: #F9EBEB; color: {self._paleta.error}; "
                f"border: 1px solid {self._paleta.error}; border-radius: 14px; padding: 4px 14px; font-weight: bold;"
            )
        else:
            self.badge_estado.setText("[ERROR CONEXION]")
            self.badge_estado.setStyleSheet(
                f"background-color: #F9EBEB; color: {self._paleta.error}; "
                f"border: 1px solid {self._paleta.error}; border-radius: 14px; padding: 4px 14px; font-weight: bold;"
            )
