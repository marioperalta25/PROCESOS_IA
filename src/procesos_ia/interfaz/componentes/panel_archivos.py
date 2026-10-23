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
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.rutas_salida import (
    resolver_ruta_disponible,
    resolver_subcarpeta_salida,
)
from procesos_ia.infraestructura.archivos.fabrica_lectores import crear_lector_flujo
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido
from procesos_ia.interfaz.responsivo import ModoPantalla


class PanelArchivos(QGroupBox):
    """Permite seleccionar el archivo tabular, explorar sus columnas y fijar la salida."""

    archivo_cargado = Signal(Path, list)  # ruta_archivo, lista_encabezados
    columnas_seleccionadas_cambiadas = Signal(list)

    def __init__(
        self,
        parent: QWidget | None = None,
        enrutador: EnrutadorSalidas | None = None,
    ) -> None:
        super().__init__("1. Datos de Entrada y Destino", parent)
        self._enrutador = enrutador or EnrutadorSalidas()
        self._ruta_entrada: Path | None = None
        self._directorio_base_salidas: Path = self._enrutador.analisis
        self._ruta_salida: Path = self._directorio_base_salidas

        self._iniciar_ui()

    @property
    def ruta_entrada(self) -> Path | None:
        return self._ruta_entrada

    @property
    def ruta_salida(self) -> Path:
        return self._ruta_salida

    @property
    def encabezados(self) -> tuple[str, ...]:
        return tuple(self.lista_columnas.item(i).text() for i in range(self.lista_columnas.count()))

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
        conectar_boton_protegido(
            self.btn_examinar_entrada,
            self._abrir_dialogo_entrada,
            "[INFO] Abriendo selector de archivo de entrada...",
            tiempo_bloqueo_ms=600,
        )
        layout_entrada.addWidget(self.btn_examinar_entrada)
        layout.addLayout(layout_entrada)

        # 2. Segmento de columnas detectadas
        layout_columnas_header = QHBoxLayout()
        self.label_columnas = QLabel("Columnas a evaluar por el modelo local (marque las deseadas):", self)
        layout_columnas_header.addWidget(self.label_columnas, stretch=1)

        self.btn_todas_cols = QPushButton("Todas", self)
        self.btn_todas_cols.setToolTip("Marcar todas las columnas")
        self.btn_todas_cols.setMinimumWidth(80)
        self.btn_todas_cols.setMaximumWidth(100)
        conectar_boton_protegido(
            self.btn_todas_cols,
            lambda: self._marcar_todas(True),
            "[INFO] Marcando todas las columnas...",
            tiempo_bloqueo_ms=400,
        )
        layout_columnas_header.addWidget(self.btn_todas_cols)

        self.btn_ninguna_cols = QPushButton("Ninguna", self)
        self.btn_ninguna_cols.setToolTip("Desmarcar todas las columnas")
        self.btn_ninguna_cols.setMinimumWidth(90)
        self.btn_ninguna_cols.setMaximumWidth(110)
        conectar_boton_protegido(
            self.btn_ninguna_cols,
            lambda: self._marcar_todas(False),
            "[INFO] Desmarcando todas las columnas...",
            tiempo_bloqueo_ms=400,
        )
        layout_columnas_header.addWidget(self.btn_ninguna_cols)

        layout.addLayout(layout_columnas_header)

        self.lista_columnas = QListWidget(self)
        self.lista_columnas.setMinimumHeight(100)
        self.lista_columnas.setMaximumHeight(450)
        self.lista_columnas.setFixedHeight(160)
        self.lista_columnas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.lista_columnas.itemChanged.connect(self._notificar_cambio_columnas)
        layout.addWidget(self.lista_columnas)

        from procesos_ia.interfaz.componentes.tirador_ajustable import TiradorRedimensionVertical
        self.tirador_columnas = TiradorRedimensionVertical(
            widget_objetivo=self.lista_columnas, altura_min=100, altura_max=450, parent=self,
        )
        layout.addWidget(self.tirador_columnas)

        # 3. Fila de seleccion de carpeta de salida
        layout_salida = QHBoxLayout()
        self.label_salida = QLabel("Carpeta de salida:", self)
        layout_salida.addWidget(self.label_salida)

        self.input_salida = QLineEdit(str(self._ruta_salida), self)
        self.input_salida.setReadOnly(True)
        layout_salida.addWidget(self.input_salida, stretch=1)

        self.btn_examinar_salida = QPushButton("Cambiar...", self)
        conectar_boton_protegido(
            self.btn_examinar_salida,
            self._abrir_dialogo_salida,
            "[INFO] Abriendo selector de carpeta de salida...",
            tiempo_bloqueo_ms=600,
        )
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

        self._ruta_salida = resolver_subcarpeta_salida(self._directorio_base_salidas, ruta)
        self.input_salida.setText(str(self._ruta_salida))

        try:
            lector = crear_lector_flujo(ruta)
            encabezados = list(lector.inicializar(ruta))

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
            "Seleccionar Directorio Base de Salida",
            str(self._directorio_base_salidas),
        )
        if directorio:
            self._directorio_base_salidas = Path(directorio)
            if self._ruta_entrada:
                self._ruta_salida = resolver_subcarpeta_salida(self._directorio_base_salidas, self._ruta_entrada)
            else:
                self._ruta_salida = resolver_ruta_disponible(self._directorio_base_salidas)
            self.input_salida.setText(str(self._ruta_salida))

    def _notificar_cambio_columnas(self) -> None:
        cols = self.obtener_columnas_seleccionadas()
        self.columnas_seleccionadas_cambiadas.emit(cols)

    def _marcar_todas(self, marcar: bool) -> None:
        estado = Qt.CheckState.Checked if marcar else Qt.CheckState.Unchecked
        self.lista_columnas.blockSignals(True)
        for i in range(self.lista_columnas.count()):
            item = self.lista_columnas.item(i)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(estado)
        self.lista_columnas.blockSignals(False)
        self._notificar_cambio_columnas()

    def adaptar_modo(self, modo: ModoPantalla) -> None:
        """Adapta etiquetas y límites de controles según el tamaño de la ventana."""
        if modo == ModoPantalla.COMPACTO:
            self.btn_examinar_entrada.setText("...")
            self.btn_examinar_salida.setText("...")
            self.label_columnas.setText("Columnas a evaluar:")
            self.btn_examinar_entrada.setMaximumWidth(60)
            self.btn_examinar_salida.setMaximumWidth(60)
            self.btn_todas_cols.setMinimumWidth(75)
            self.btn_ninguna_cols.setMinimumWidth(85)
        elif modo == ModoPantalla.AMPLIO:
            self.btn_examinar_entrada.setText("Examinar...")
            self.btn_examinar_salida.setText("Examinar...")
            self.label_columnas.setText("Columnas a evaluar por el modelo local (marque las deseadas):")
            self.btn_examinar_entrada.setMaximumWidth(150)
            self.btn_examinar_salida.setMaximumWidth(150)
            self.btn_todas_cols.setMinimumWidth(85)
            self.btn_ninguna_cols.setMinimumWidth(95)
        else:
            self.btn_examinar_entrada.setText("Examinar...")
            self.btn_examinar_salida.setText("Examinar...")
            self.label_columnas.setText("Columnas a evaluar por el modelo local (marque las deseadas):")
            self.btn_examinar_entrada.setMaximumWidth(130)
            self.btn_examinar_salida.setMaximumWidth(130)
            self.btn_todas_cols.setMinimumWidth(80)
            self.btn_ninguna_cols.setMinimumWidth(90)
