"""Panel para selección de archivos de entrada, detección de columnas y destino de salida."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
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

from procesos_ia.infraestructura.archivos.fabrica_lectores import crear_lector_flujo


class PanelArchivos(QGroupBox):
    """Permite seleccionar el archivo tabular, explorar sus columnas y fijar la salida."""

    archivo_cargado = Signal(Path, list)  # ruta_archivo, lista_encabezados
    columnas_seleccionadas_cambiadas = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("1. Datos de Entrada y Destino", parent)
        self._ruta_entrada: Path | None = None
        self._ruta_salida: Path = Path.home() / "Desktop" / "procesos_ia_salidas"

        self._iniciar_ui()

    @property
    def ruta_entrada(self) -> Path | None:
        return self._ruta_entrada

    @property
    def ruta_salida(self) -> Path:
        return self._ruta_salida

    def obtener_columnas_seleccionadas(self) -> list[str]:
        """Devuelve los nombres de las columnas marcadas por el usuario."""
        cols: list[str] = []
        for i in range(self.lista_columnas.count()):
            item = self.lista_columnas.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                cols.append(item.text())
        return cols

    def _iniciar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 1. Fila de seleccion de archivo de entrada
        layout_entrada = QHBoxLayout()
        self.input_entrada = QLineEdit(self)
        self.input_entrada.setReadOnly(True)
        self.input_entrada.setPlaceholderText("Seleccione archivo tabular (.csv, .xlsx, .txt)...")
        layout_entrada.addWidget(self.input_entrada, stretch=1)

        self.btn_examinar_entrada = QPushButton("Examinar...", self)
        self.btn_examinar_entrada.clicked.connect(self._abrir_dialogo_entrada)
        layout_entrada.addWidget(self.btn_examinar_entrada)
        layout.addLayout(layout_entrada)

        # 2. Selector de columnas detectadas
        self.label_columnas = QLabel("Columnas a evaluar por el modelo local (marque las deseadas):", self)
        layout.addWidget(self.label_columnas)

        self.lista_columnas = QListWidget(self)
        self.lista_columnas.setMaximumHeight(90)
        self.lista_columnas.itemChanged.connect(self._notificar_cambio_columnas)
        layout.addWidget(self.lista_columnas)

        # 3. Fila de seleccion de carpeta de salida
        layout_salida = QHBoxLayout()
        self.label_salida = QLabel("Carpeta de salida:", self)
        layout_salida.addWidget(self.label_salida)

        self.input_salida = QLineEdit(str(self._ruta_salida), self)
        self.input_salida.setReadOnly(True)
        layout_salida.addWidget(self.input_salida, stretch=1)

        self.btn_examinar_salida = QPushButton("Cambiar...", self)
        self.btn_examinar_salida.clicked.connect(self._abrir_dialogo_salida)
        layout_salida.addWidget(self.btn_examinar_salida)
        layout.addLayout(layout_salida)

    def _abrir_dialogo_entrada(self) -> None:
        filtros = "Archivos Tabulares (*.csv *.xlsx *.txt);;CSV (*.csv);;Excel (*.xlsx);;Texto (*.txt);;Todos (*.*)"
        seleccion, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar Archivo de Entrada",
            str(Path.home()),
            filtros,
        )
        if seleccion:
            self.cargar_archivo(Path(seleccion))

    def cargar_archivo(self, ruta: Path) -> None:
        """Carga el archivo, actualiza el campo de texto y puebla la lista de columnas."""
        self._ruta_entrada = ruta
        self.input_entrada.setText(str(ruta))
        self.lista_columnas.clear()

        try:
            lector = crear_lector_flujo(ruta)
            encabezados = list(lector.obtener_encabezados(ruta))

            for enc in encabezados:
                item = QListWidgetItem(enc, self.lista_columnas)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)

            self.archivo_cargado.emit(ruta, encabezados)
            self._notificar_cambio_columnas()
        except Exception as error:
            item = QListWidgetItem(f"[ERROR] No se pudo leer encabezados: {error}")
            self.lista_columnas.addItem(item)

    def _abrir_dialogo_salida(self) -> None:
        directorio = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar Directorio de Salida",
            str(self._ruta_salida),
        )
        if directorio:
            self._ruta_salida = Path(directorio)
            self.input_salida.setText(str(self._ruta_salida))

    def _notificar_cambio_columnas(self) -> None:
        cols = self.obtener_columnas_seleccionadas()
        self.columnas_seleccionadas_cambiadas.emit(cols)
