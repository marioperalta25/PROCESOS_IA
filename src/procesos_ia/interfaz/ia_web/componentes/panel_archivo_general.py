"""Panel para seleccion de archivo tabular CSV y seleccion de columnas en IA General."""

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
    QVBoxLayout,
    QWidget,
)

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.infraestructura.archivos.fabrica_lectores import (
    crear_lector_flujo,
    obtener_hojas_excel,
)
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido


class PanelArchivoGeneral(QGroupBox):
    """Permite seleccionar CSV, listar y elegir columnas para evaluar con delimitador |."""

    archivo_cargado = Signal(Path, list)
    log_notificado = Signal(str)

    def __init__(self, parent: QWidget | None = None, enrutador: EnrutadorSalidas | None = None) -> None:
        super().__init__("Gestión de Archivo Tabular y Columnas", parent)
        self._enrutador = enrutador or EnrutadorSalidas()
        self._ruta_csv: Path | None = None
        self._columnas: list[str] = []
        self._iniciar_ui()

    def _iniciar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.lbl_guia_archivo = QLabel("[INFO] 1. Archivo: Seleccione un archivo CSV o Excel para extracción con Google Lens.", self)
        self.lbl_guia_archivo.setStyleSheet("color: #58615B; font-size: 11px;")
        layout.addWidget(self.lbl_guia_archivo)

        # 1. Fila de seleccion de archivo
        layout_archivo = QHBoxLayout()
        self.input_ruta = QLineEdit(self)
        self.input_ruta.setMinimumHeight(28)
        self.input_ruta.setPlaceholderText("Seleccionar archivo .csv o .xlsx con datos...")
        self.btn_examinar = QPushButton("Examinar...", self)
        self.btn_examinar.setMinimumHeight(28)
        conectar_boton_protegido(
            self.btn_examinar, self._abrir_dialogo_archivo,
            "[INFO] Seleccionando archivo...", tiempo_bloqueo_ms=500
        )
        layout_archivo.addWidget(self.input_ruta, stretch=1)
        layout_archivo.addWidget(self.btn_examinar)
        layout.addLayout(layout_archivo)

        # Selector de hoja Excel (aparece cuando el libro tiene varias hojas)
        self.layout_hoja = QHBoxLayout()
        self.lbl_hoja = QLabel("Hoja de Excel a procesar:", self)
        self.lbl_hoja.setStyleSheet("font-weight: bold;")
        self.combo_hojas = QComboBox(self)
        self.combo_hojas.setMinimumHeight(28)
        self.combo_hojas.currentTextChanged.connect(self._al_cambiar_hoja)
        self.layout_hoja.addWidget(self.lbl_hoja)
        self.layout_hoja.addWidget(self.combo_hojas, stretch=1)
        self.lbl_hoja.setVisible(False)
        self.combo_hojas.setVisible(False)
        layout.addLayout(self.layout_hoja)

        # 2. Acciones de columnas
        layout_acciones = QHBoxLayout()
        self.lbl_columnas = QLabel("Columnas del archivo:", self)
        layout_acciones.addWidget(self.lbl_columnas)
        layout_acciones.addStretch()

        self.btn_todas = QPushButton("Todas", self)
        self.btn_todas.setMinimumHeight(26); self.btn_todas.setMinimumWidth(75)
        conectar_boton_protegido(self.btn_todas, self._marcar_todas, "[INFO] Marcando todas las columnas...", tiempo_bloqueo_ms=300)
        self.btn_ninguna = QPushButton("Ninguna", self)
        self.btn_ninguna.setMinimumHeight(26); self.btn_ninguna.setMinimumWidth(85)
        conectar_boton_protegido(self.btn_ninguna, self._desmarcar_todas, "[INFO] Desmarcando todas las columnas...", tiempo_bloqueo_ms=300)
        layout_acciones.addWidget(self.btn_todas)
        layout_acciones.addWidget(self.btn_ninguna)
        layout.addLayout(layout_acciones)

        # 3. Lista con checkboxes y tirador
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
        if hasattr(self, "lbl_guia_archivo"):
            self.lbl_guia_archivo.setText("[INFO] 1. Archivo Lens" if es_compacto else "[INFO] 1. Archivo: Seleccione un archivo CSV o Excel para extracción con Google Lens.")

    def _abrir_dialogo_archivo(self) -> None:
        self._enrutador.datos.mkdir(parents=True, exist_ok=True)
        ruta, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar Archivo Tabular",
            str(self._enrutador.datos),
            "Archivos Tabulares (*.csv *.xlsx *.xlsm);;Archivos CSV (*.csv);;Archivos Excel (*.xlsx *.xlsm);;Todos los archivos (*.*)",
        )
        if ruta:
            self.cargar_archivo(Path(ruta))

    def cargar_archivo(self, ruta: Path) -> None:
        """Carga y analiza los encabezados de un archivo CSV o Excel sin sobrecargar RAM."""
        self._ruta_csv = ruta
        self.input_ruta.setText(str(ruta))

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
            self.log_notificado.emit(f"[INFO] Excel con {len(hojas)} hojas detectadas. Hoja activa: '{hojas[0]}'.")
            self._leer_columnas_de_hoja(ruta, hojas[0])
        else:
            self.lbl_hoja.setVisible(False)
            self.combo_hojas.setVisible(False)
            self.combo_hojas.blockSignals(False)
            hoja_unica = hojas[0] if hojas else None
            self._leer_columnas_de_hoja(ruta, hoja_unica)

    def _al_cambiar_hoja(self, hoja: str) -> None:
        if not self._ruta_csv or not hoja:
            return
        self._leer_columnas_de_hoja(self._ruta_csv, hoja)
        self.log_notificado.emit(f"[INFO] Hoja seleccionada: '{hoja}'. Columnas actualizadas.")

    def _leer_columnas_de_hoja(self, ruta: Path, nombre_hoja: str | None) -> None:
        """Inspecciona únicamente las primeras 5 filas de la hoja solicitada."""
        self.lista_columnas.clear()
        self.combo_columna_img.clear()
        self.combo_columna_img.addItem("(Ninguna)", "")

        try:
            lector = crear_lector_flujo(ruta, nombre_hoja_excel=nombre_hoja)
            encabezados_detectados = lector.inicializar(ruta)
            self._columnas = [h.strip() for h in encabezados_detectados if h.strip()]

            for col in self._columnas:
                item = QListWidgetItem(col)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                self.lista_columnas.addItem(item)
                self.combo_columna_img.addItem(col, col)

            indice_auto = -1
            if len(self._columnas) == 1:
                indice_auto = 1
            else:
                patrones_url = ("url", "link", "imagen", "image", "foto", "tarjeta", "img", "picture")
                for idx, col in enumerate(self._columnas, start=1):
                    if any(p in col.lower() for p in patrones_url):
                        indice_auto = idx
                        break
            if indice_auto > 0:
                self.combo_columna_img.setCurrentIndex(indice_auto)

            hoja_txt = f" (hoja '{nombre_hoja}')" if nombre_hoja else ""
            msg = f"[OK] Archivo cargado: {ruta.name}{hoja_txt} con {len(self._columnas)} columnas"
            self.log_notificado.emit(msg)
            self.archivo_cargado.emit(ruta, self._columnas)
        except Exception as error:
            self.log_notificado.emit(f"[ERROR] No se pudo leer columnas del archivo: {error}")

    def _marcar_todas(self) -> None:
        for i in range(self.lista_columnas.count()):
            self.lista_columnas.item(i).setCheckState(Qt.CheckState.Checked)

    def _desmarcar_todas(self) -> None:
        for i in range(self.lista_columnas.count()):
            self.lista_columnas.item(i).setCheckState(Qt.CheckState.Unchecked)

    @property
    def columnas(self) -> list[str]:
        return list(self._columnas)

    def obtener_ruta_csv(self) -> Path | None:
        return self._ruta_csv

    def obtener_hoja_seleccionada(self) -> str | None:
        if self.combo_hojas.isVisible() and self.combo_hojas.currentText():
            return self.combo_hojas.currentText().strip()
        return None

    def obtener_columnas_seleccionadas(self) -> list[str]:
        return [self.lista_columnas.item(i).text() for i in range(self.lista_columnas.count())
                if self.lista_columnas.item(i).checkState() == Qt.CheckState.Checked]

    def obtener_columna_imagen(self) -> str:
        seleccionada = str(self.combo_columna_img.currentData() or "")
        if not seleccionada:
            cols_activas = self.obtener_columnas_seleccionadas()
            if len(cols_activas) == 1:
                return cols_activas[0]
            if len(self._columnas) == 1:
                return self._columnas[0]
        return seleccionada

    def limpiar(self) -> None:
        """Restablece los campos a su estado inicial."""
        self._ruta_csv = None
        self._columnas.clear()
        self.input_ruta.clear()
        self.combo_hojas.clear()
        self.lbl_hoja.setVisible(False)
        self.combo_hojas.setVisible(False)
        self.lista_columnas.clear()
        self.combo_columna_img.clear()
        self.combo_columna_img.addItem("(Ninguna)", "")
