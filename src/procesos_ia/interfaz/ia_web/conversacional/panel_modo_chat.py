"""Panel modular especializado para la configuracion de IA General en Modo Chat."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.visual_1a1.procesador_archivo_urls import (
    leer_filas_archivo_tabular,
)
from procesos_ia.interfaz.componentes.editor_texto_expandible import (
    EditorTextoExpandible,
)
from procesos_ia.interfaz.componentes.tirador_ajustable import (
    TiradorRedimensionVertical,
)
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido


class PanelModoChat(QWidget):
    """Componente especializado para evaluar lotes CSV/XLSX con delimitador pipe y prompt."""

    log_notificado = Signal(str)

    def __init__(
        self,
        servicio_prompts: object | None = None,
        enrutador: EnrutadorSalidas | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._enrutador = enrutador or EnrutadorSalidas()
        self._servicio_prompts = servicio_prompts
        self._ruta_archivo: Path | None = None
        self._columnas: list[str] = []
        self._iniciar_ui()
        self._cargar_plantillas()

    def _iniciar_ui(self) -> None:
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(8)

        # 1. Gestion de Archivo Tabular y Columnas (exclusivo checkboxes)
        grupo_archivo = QGroupBox("Gestión de Archivo Tabular y Columnas", self)
        layout_g = QVBoxLayout(grupo_archivo)
        layout_g.setContentsMargins(8, 8, 8, 8)
        layout_g.setSpacing(6)

        layout_sel = QHBoxLayout()
        self.input_ruta = QLineEdit(self)
        self.input_ruta.setMinimumHeight(28)
        self.input_ruta.setPlaceholderText("Seleccionar archivo .csv o .xlsx con datos...")
        self.btn_examinar = QPushButton("Examinar...", self)
        self.btn_examinar.setMinimumHeight(28)
        conectar_boton_protegido(
            self.btn_examinar,
            self._abrir_dialogo_archivo,
            "[INFO] Seleccionando archivo...",
            tiempo_bloqueo_ms=500,
        )
        layout_sel.addWidget(self.input_ruta, stretch=1)
        layout_sel.addWidget(self.btn_examinar)
        layout_g.addLayout(layout_sel)

        layout_acciones = QHBoxLayout()
        self.lbl_columnas = QLabel("Columnas del archivo para evaluar con |:", self)
        layout_acciones.addWidget(self.lbl_columnas)
        layout_acciones.addStretch()

        self.btn_todas = QPushButton("Todas", self)
        self.btn_todas.setMinimumHeight(26)
        self.btn_todas.setMinimumWidth(75)
        self.btn_todas.clicked.connect(self._marcar_todas)
        self.btn_ninguna = QPushButton("Ninguna", self)
        self.btn_ninguna.setMinimumHeight(26)
        self.btn_ninguna.setMinimumWidth(85)
        self.btn_ninguna.clicked.connect(self._desmarcar_todas)
        layout_acciones.addWidget(self.btn_todas)
        layout_acciones.addWidget(self.btn_ninguna)
        layout_g.addLayout(layout_acciones)

        self.lista_columnas = QListWidget(self)
        self.lista_columnas.setMinimumHeight(75)
        self.lista_columnas.setMaximumHeight(350)
        self.lista_columnas.setFixedHeight(95)
        layout_g.addWidget(self.lista_columnas)

        self.tirador_columnas = TiradorRedimensionVertical(
            widget_objetivo=self.lista_columnas,
            altura_min=75,
            altura_max=350,
            parent=self,
        )
        layout_g.addWidget(self.tirador_columnas)
        layout_principal.addWidget(grupo_archivo)

        # 2. Plantillas e Instrucciones
        grupo_prompt = QGroupBox("Plantillas IA Web e Instrucciones", self)
        layout_p = QVBoxLayout(grupo_prompt)
        layout_p.setContentsMargins(8, 8, 8, 8)
        layout_p.setSpacing(6)

        layout_combo = QHBoxLayout()
        layout_combo.addWidget(QLabel("Plantilla IA Web:", self))
        self.combo_plantillas = QComboBox(self)
        self.combo_plantillas.currentIndexChanged.connect(self._al_seleccionar_plantilla)
        layout_combo.addWidget(self.combo_plantillas, stretch=1)
        layout_p.addLayout(layout_combo)

        self.txt_instrucciones = EditorTextoExpandible(
            altura_inicial=120,
            placeholder="Instrucciones para Modo IA (ej. Extrae el sentimiento, califica el lead)...",
            parent=self,
        )
        layout_p.addWidget(self.txt_instrucciones)

        layout_lote = QHBoxLayout()
        layout_lote.addWidget(QLabel("Filas por lote:", self))
        self.spin_lote = QSpinBox(self)
        self.spin_lote.setRange(1, 50)
        self.spin_lote.setValue(5)
        layout_lote.addWidget(self.spin_lote)
        layout_lote.addStretch()
        layout_p.addLayout(layout_lote)
        layout_principal.addWidget(grupo_prompt)

    def _abrir_dialogo_archivo(self) -> None:
        self._enrutador.datos.mkdir(parents=True, exist_ok=True)
        ruta, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar Archivo Tabular",
            str(self._enrutador.datos),
            "Archivos Tabulares (*.csv *.xlsx *.xlsm);;Archivos CSV (*.csv);;Archivos Excel (*.xlsx *.xlsm);;Todos (*.*)",
        )
        if ruta:
            self.cargar_archivo(Path(ruta))

    def cargar_archivo(self, ruta: Path) -> None:
        """Carga y desglosa las columnas del archivo tabular."""
        self._ruta_archivo = ruta
        self.input_ruta.setText(str(ruta))
        self.lista_columnas.clear()

        try:
            from procesos_ia.infraestructura.archivos.fabrica_lectores import crear_lector_flujo
            lector = crear_lector_flujo(ruta)
            encabezados = lector.inicializar(ruta)
            self._columnas = [h.strip() for h in encabezados if h.strip()]

            for col in self._columnas:
                item = QListWidgetItem(col)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                self.lista_columnas.addItem(item)

            self.log_notificado.emit(
                f"[OK] Archivo cargado: {ruta.name} con {len(self._columnas)} columnas"
            )
        except Exception as error:
            self.log_notificado.emit(f"[ERROR] No se pudo leer columnas del archivo: {error}")

    def _marcar_todas(self) -> None:
        for i in range(self.lista_columnas.count()):
            self.lista_columnas.item(i).setCheckState(Qt.CheckState.Checked)

    def _desmarcar_todas(self) -> None:
        for i in range(self.lista_columnas.count()):
            self.lista_columnas.item(i).setCheckState(Qt.CheckState.Unchecked)

    def _cargar_plantillas(self) -> None:
        self.combo_plantillas.clear()
        self.combo_plantillas.addItem("(Escribir prompt personalizado...)", "")
        if not self._servicio_prompts:
            return
        try:
            from procesos_ia.aplicacion.ia_web.comun.prompts_ia_web import asegurar_plantillas_ia_web
            asegurar_plantillas_ia_web(self._servicio_prompts)
            for p in self._servicio_prompts.listar_plantillas(categoria="ia_web"):
                self.combo_plantillas.addItem(f"{p.titulo}", p.contenido)
        except Exception:
            pass

    def _al_seleccionar_plantilla(self) -> None:
        contenido = self.combo_plantillas.currentData()
        if contenido:
            self.txt_instrucciones.setPlainText(str(contenido))
            self.log_notificado.emit(
                f"[INFO] Plantilla IA Web cargada: {self.combo_plantillas.currentText()}"
            )

    def obtener_ruta_archivo(self) -> Path | None:
        return self._ruta_archivo

    def obtener_columnas_seleccionadas(self) -> list[str]:
        return [
            self.lista_columnas.item(i).text()
            for i in range(self.lista_columnas.count())
            if self.lista_columnas.item(i).checkState() == Qt.CheckState.Checked
        ]

    def obtener_instrucciones(self) -> str:
        return self.txt_instrucciones.toPlainText().strip()

    def obtener_tamano_lote(self) -> int:
        return self.spin_lote.value()

    def obtener_parametros(self) -> dict[str, Any] | None:
        """Valida y estructura los parametros listos para HiloIAGeneral."""
        if not self._ruta_archivo or not self._ruta_archivo.exists():
            return None
        filas = leer_filas_archivo_tabular(self._ruta_archivo)
        return {
            "filas": filas,
            "instrucciones": self.obtener_instrucciones() or "Evalúa los registros según su información.",
            "columnas": self.obtener_columnas_seleccionadas(),
            "tamano_lote": self.obtener_tamano_lote(),
            "nombre_salida": self._ruta_archivo.stem,
        }

    def limpiar(self) -> None:
        """Restablece los campos del panel a su estado inicial."""
        self._ruta_archivo = None
        self._columnas.clear()
        self.input_ruta.clear()
        self.lista_columnas.clear()
        self.txt_instrucciones.clear()
        self.combo_plantillas.setCurrentIndex(0)
        self.spin_lote.setValue(5)
