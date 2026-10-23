"""Panel para seleccion de archivo tabular CSV y seleccion de columnas en IA General."""

from __future__ import annotations

import csv
from pathlib import Path
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
    QVBoxLayout,
    QWidget,
)

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido


class PanelArchivoGeneral(QGroupBox):
    """Permite seleccionar CSV, listar y elegir columnas para evaluar con delimitador |."""

    archivo_cargado = Signal(Path, list)
    log_notificado = Signal(str)

    def __init__(self, parent: QWidget | None = None, enrutador: EnrutadorSalidas | None = None) -> None:
        super().__init__("Gestión de Archivo CSV y Columnas", parent)
        self._enrutador = enrutador or EnrutadorSalidas()
        self._ruta_csv: Path | None = None
        self._columnas: list[str] = []
        self._iniciar_ui()

    def _iniciar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 1. Fila de seleccion de archivo
        layout_archivo = QHBoxLayout()
        self.input_ruta = QLineEdit(self)
        self.input_ruta.setMinimumHeight(28)
        self.input_ruta.setPlaceholderText("Seleccionar archivo .csv con datos...")
        self.btn_examinar = QPushButton("Examinar...", self)
        self.btn_examinar.setMinimumHeight(28)
        conectar_boton_protegido(
            self.btn_examinar, self._abrir_dialogo_archivo,
            "[INFO] Seleccionando CSV...", tiempo_bloqueo_ms=500
        )
        layout_archivo.addWidget(self.input_ruta, stretch=1)
        layout_archivo.addWidget(self.btn_examinar)
        layout.addLayout(layout_archivo)

        # 2. Acciones de columnas
        layout_acciones = QHBoxLayout()
        self.lbl_columnas = QLabel("Columnas a evaluar con delimitador '|':", self)
        layout_acciones.addWidget(self.lbl_columnas)
        layout_acciones.addStretch()

        self.btn_todas = QPushButton("Todas", self)
        self.btn_todas.setMinimumHeight(26); self.btn_todas.setMinimumWidth(75)
        self.btn_todas.clicked.connect(self._marcar_todas)
        self.btn_ninguna = QPushButton("Ninguna", self)
        self.btn_ninguna.setMinimumHeight(26); self.btn_ninguna.setMinimumWidth(85)
        self.btn_ninguna.clicked.connect(self._desmarcar_todas)
        layout_acciones.addWidget(self.btn_todas)
        layout_acciones.addWidget(self.btn_ninguna)
        layout.addLayout(layout_acciones)

        # 3. Lista con checkboxes (con tirador de arrastre con cursor SizeVerCursor)
        self.lista_columnas = QListWidget(self)
        self.lista_columnas.setMinimumHeight(75)
        self.lista_columnas.setMaximumHeight(350)
        self.lista_columnas.setFixedHeight(95)
        layout.addWidget(self.lista_columnas)

        from procesos_ia.interfaz.componentes.tirador_ajustable import TiradorRedimensionVertical
        self.tirador_columnas = TiradorRedimensionVertical(
            widget_objetivo=self.lista_columnas, altura_min=75, altura_max=350, parent=self,
        )
        layout.addWidget(self.tirador_columnas)

        self.fila_columna_img = QWidget(self)
        layout_img = QHBoxLayout(self.fila_columna_img)
        layout_img.setContentsMargins(0, 0, 0, 0)
        layout_img.addWidget(QLabel("Columna de Imagen/URL:", self))
        self.combo_columna_img = QComboBox(self)
        self.combo_columna_img.setMinimumHeight(26)
        self.combo_columna_img.addItem("(Ninguna)", "")
        layout_img.addWidget(self.combo_columna_img, stretch=1)
        layout.addWidget(self.fila_columna_img)

    def configurar_modo_imagen(self, habilitado: bool) -> None:
        """Muestra u oculta el selector de columna de imagen según la operación."""
        self.fila_columna_img.setVisible(habilitado)

    def adaptar_modo(self, modo: object) -> None:
        """Adapta la disposicion interna si la pantalla es reducida."""
        es_compacto = getattr(modo, "value", str(modo)) == "compacto"
        self.btn_todas.setText("All" if es_compacto else "Todas")
        self.btn_ninguna.setText("None" if es_compacto else "Ninguna")

    def _abrir_dialogo_archivo(self) -> None:
        self._enrutador.datos.mkdir(parents=True, exist_ok=True)
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Archivo CSV", str(self._enrutador.datos), "Archivos CSV (*.csv)"
        )
        if ruta:
            self.cargar_archivo(Path(ruta))

    def cargar_archivo(self, ruta: Path) -> None:
        """Carga y analiza los encabezados de un archivo CSV."""
        self._ruta_csv = ruta
        self.input_ruta.setText(str(ruta))
        self.lista_columnas.clear()
        self.combo_columna_img.clear()
        self.combo_columna_img.addItem("(Ninguna)", "")

        try:
            with open(ruta, mode="r", encoding="utf-8-sig", errors="ignore") as f:
                lector = csv.reader(f)
                headers = next(lector, [])
            self._columnas = [h.strip() for h in headers if h.strip()]

            for col in self._columnas:
                item = QListWidgetItem(col)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                self.lista_columnas.addItem(item)
                self.combo_columna_img.addItem(col, col)

            msg = f"[OK] Archivo CSV cargado: {ruta.name} con {len(self._columnas)} columnas"
            self.log_notificado.emit(msg)
            self.archivo_cargado.emit(ruta, self._columnas)
        except Exception as error:
            self.log_notificado.emit(f"[ERROR] No se pudo leer columnas del CSV: {error}")

    def _marcar_todas(self) -> None:
        for i in range(self.lista_columnas.count()):
            self.lista_columnas.item(i).setCheckState(Qt.CheckState.Checked)

    def _desmarcar_todas(self) -> None:
        for i in range(self.lista_columnas.count()):
            self.lista_columnas.item(i).setCheckState(Qt.CheckState.Unchecked)

    def obtener_ruta_csv(self) -> Path | None:
        return self._ruta_csv

    def obtener_columnas_seleccionadas(self) -> list[str]:
        seleccionadas: list[str] = []
        for i in range(self.lista_columnas.count()):
            item = self.lista_columnas.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                seleccionadas.append(item.text())
        return seleccionadas

    def obtener_columna_imagen(self) -> str:
        return str(self.combo_columna_img.currentData() or "")
