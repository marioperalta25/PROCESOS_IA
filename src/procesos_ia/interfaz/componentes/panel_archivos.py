"""Panel para selección de archivos de entrada, detección de columnas y destino de salida."""

from __future__ import annotations

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
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.rutas_salida import (
    resolver_ruta_disponible,
    resolver_subcarpeta_salida,
)
from procesos_ia.infraestructura.archivos.fabrica_lectores import (
    crear_lector_flujo,
    obtener_hojas_excel,
)
from procesos_ia.interfaz.componentes.tirador_ajustable import TiradorRedimensionVertical
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido
from procesos_ia.interfaz.responsivo import ModoPantalla


class PanelArchivos(QGroupBox):
    """Permite seleccionar el archivo tabular, explorar sus columnas y fijar la salida."""

    archivo_cargado = Signal(Path, list)
    columnas_seleccionadas_cambiadas = Signal(list)

    def __init__(
        self,
        parent: QWidget | None = None,
        enrutador: EnrutadorSalidas | None = None,
    ) -> None:
        super().__init__("1. Datos de Entrada y Destino", parent)
        self._enrutador = enrutador or EnrutadorSalidas()
        self._ruta_entrada: Path | None = None
        self._raiz_salidas = self._enrutador.raiz
        gestor = self._enrutador.gestor_procesos()
        self._directorio_base_salidas = gestor.rama("ia_local") / gestor.configuracion["estados"]["en_proceso"]
        self._ruta_salida: Path = self._directorio_base_salidas
        self._iniciar_ui()

    @property
    def ruta_entrada(self) -> Path | None:
        return self._ruta_entrada

    @property
    def ruta_salida(self) -> Path:
        return self._ruta_salida

    @property
    def raiz_salidas(self) -> Path:
        return self._raiz_salidas

    def mostrar_destino_salida(self, directorio: Path) -> None:
        self._ruta_salida = directorio
        self.input_salida.setText(str(directorio))

    @property
    def encabezados(self) -> tuple[str, ...]:
        return tuple(self.lista_columnas.item(i).text() for i in range(self.lista_columnas.count()))

    def obtener_hoja_seleccionada(self) -> str | None:
        if self.combo_hojas.isVisible() and self.combo_hojas.currentText():
            return self.combo_hojas.currentText().strip()
        return None

    def obtener_columnas_seleccionadas(self) -> list[str]:
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
            self.btn_examinar_entrada, self._abrir_dialogo_entrada,
            "[INFO] Abriendo selector...", tiempo_bloqueo_ms=600,
        )
        layout_entrada.addWidget(self.btn_examinar_entrada)
        layout.addLayout(layout_entrada)

        # Fila de seleccion de hoja Excel (aparece si tiene > 1 hoja)
        self.layout_hoja = QHBoxLayout()
        self.lbl_hoja = QLabel("Hoja de Excel:", self)
        self.lbl_hoja.setStyleSheet("font-weight: bold;")
        self.combo_hojas = QComboBox(self)
        self.combo_hojas.setMinimumHeight(28)
        self.combo_hojas.currentTextChanged.connect(self._al_cambiar_hoja)
        self.layout_hoja.addWidget(self.lbl_hoja)
        self.layout_hoja.addWidget(self.combo_hojas, stretch=1)
        self.lbl_hoja.setVisible(False)
        self.combo_hojas.setVisible(False)
        layout.addLayout(self.layout_hoja)

        # 2. Segmento de columnas detectadas
        layout_columnas_header = QHBoxLayout()
        self.label_columnas = QLabel("Columnas a evaluar por el modelo local (marque las deseadas):", self)
        layout_columnas_header.addWidget(self.label_columnas, stretch=1)

        self.btn_todas_cols = QPushButton("Todas", self)
        self.btn_todas_cols.setMinimumWidth(80); self.btn_todas_cols.setMaximumWidth(100)
        conectar_boton_protegido(self.btn_todas_cols, lambda: self._marcar_todas(True), "[INFO]...", 400)
        layout_columnas_header.addWidget(self.btn_todas_cols)

        self.btn_ninguna_cols = QPushButton("Ninguna", self)
        self.btn_ninguna_cols.setMinimumWidth(90); self.btn_ninguna_cols.setMaximumWidth(110)
        conectar_boton_protegido(self.btn_ninguna_cols, lambda: self._marcar_todas(False), "[INFO]...", 400)
        layout_columnas_header.addWidget(self.btn_ninguna_cols)
        layout.addLayout(layout_columnas_header)

        self.lista_columnas = QListWidget(self)
        self.lista_columnas.setMinimumHeight(100)
        self.lista_columnas.setMaximumHeight(450)
        self.lista_columnas.setFixedHeight(160)
        self.lista_columnas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.lista_columnas.itemChanged.connect(self._notificar_cambio_columnas)
        layout.addWidget(self.lista_columnas)

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
        conectar_boton_protegido(self.btn_examinar_salida, self._abrir_dialogo_salida, "[INFO]...", 600)
        layout_salida.addWidget(self.btn_examinar_salida)
        layout.addLayout(layout_salida)

    def _abrir_dialogo_entrada(self) -> None:
        filtros = "Archivos Tabulares (*.csv *.xlsx *.xlsm *.txt);;CSV (*.csv);;Excel (*.xlsx *.xlsm);;Texto (*.txt);;Todos (*.*)"
        origen = str(self._enrutador.datos) if self._enrutador.datos.exists() else str(Path.home())
        seleccion, _ = QFileDialog.getOpenFileName(self, "Seleccionar Archivo de Entrada", origen, filtros)
        if seleccion:
            self.cargar_archivo(Path(seleccion))

    def cargar_archivo(self, ruta: Path) -> None:
        """Carga el archivo detectando hojas de Excel de forma ligera."""
        self._ruta_entrada = ruta
        self.input_entrada.setText(str(ruta))

        self._ruta_salida = resolver_subcarpeta_salida(self._directorio_base_salidas, ruta)
        self.input_salida.setText(str(self._ruta_salida))

        hojas: list[str] = []
        if ruta.suffix.lower() in (".xlsx", ".xlsm"):
            hojas = obtener_hojas_excel(ruta)

        self.combo_hojas.blockSignals(True)
        self.combo_hojas.clear()
        if len(hojas) > 1:
            self.combo_hojas.addItems(hojas)
            self.lbl_hoja.setVisible(True)
            self.combo_hojas.setVisible(True)
            self.combo_hojas.blockSignals(False)
            self._leer_columnas_hoja(ruta, hojas[0])
        else:
            self.lbl_hoja.setVisible(False)
            self.combo_hojas.setVisible(False)
            self.combo_hojas.blockSignals(False)
            hoja_unica = hojas[0] if hojas else None
            self._leer_columnas_hoja(ruta, hoja_unica)

    def _al_cambiar_hoja(self, hoja: str) -> None:
        if not self._ruta_entrada or not hoja:
            return
        self._leer_columnas_hoja(self._ruta_entrada, hoja)

    def _leer_columnas_hoja(self, ruta: Path, nombre_hoja: str | None) -> None:
        """Lee únicamente los encabezados de las primeras 5 filas de la hoja."""
        self.lista_columnas.clear()
        try:
            lector = crear_lector_flujo(ruta, nombre_hoja_excel=nombre_hoja)
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
            self, "Seleccionar Directorio Base de Salida", str(self._directorio_base_salidas)
        )
        if directorio:
            self._raiz_salidas = Path(directorio)
            gestor = self._enrutador.gestor_procesos(self._raiz_salidas)
            self._directorio_base_salidas = gestor.rama("ia_local") / gestor.configuracion["estados"]["en_proceso"]
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
        es_compacto = modo == ModoPantalla.COMPACTO
        self.btn_todas_cols.setText("All" if es_compacto else "Todas")
        self.btn_ninguna_cols.setText("None" if es_compacto else "Ninguna")
        if es_compacto:
            self.btn_examinar_entrada.setText("...")
            self.btn_examinar_entrada.setMaximumWidth(60)
        elif modo == ModoPantalla.ESTANDAR:
            self.btn_examinar_entrada.setText("Examinar...")
            self.btn_examinar_entrada.setMaximumWidth(130)
        else:
            self.btn_examinar_entrada.setText("Examinar...")
            self.btn_examinar_entrada.setMaximumWidth(150)
