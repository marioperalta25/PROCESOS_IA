"""Panel modular especializado para la configuracion de IA General en Modo Chat."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.visual_1a1.procesador_archivo_urls import leer_filas_archivo_tabular
from procesos_ia.infraestructura.archivos.fabrica_lectores import crear_lector_flujo, obtener_hojas_excel
from procesos_ia.interfaz.componentes.editor_texto_expandible import EditorTextoExpandible
from procesos_ia.interfaz.componentes.tirador_ajustable import TiradorRedimensionVertical
from procesos_ia.interfaz.ia_web.conversacional.medidor_tokens import EtiquetaContadorTokens, LIMITE_CARACTERES_MODO_IA
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido
from procesos_ia.interfaz.responsivo import ModoPantalla


class PanelModoChat(QWidget):
    """Componente especializado para evaluar lotes CSV/XLSX con delimitador pipe y prompt."""

    log_notificado = Signal(str)
    plantillas_solicitadas = Signal()

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
        layout_principal.setSpacing(6)

        # 1. Gestion de Archivo Tabular y Columnas
        grupo_archivo = QGroupBox("Gestión de Archivo Tabular y Columnas", self)
        layout_g = QVBoxLayout(grupo_archivo)
        layout_g.setContentsMargins(8, 8, 8, 8); layout_g.setSpacing(4)

        self.lbl_guia_archivo = QLabel("[INFO] 1. Archivo: Seleccione el archivo CSV o Excel a clasificar.", self)
        self.lbl_guia_archivo.setStyleSheet("color: #58615B; font-size: 11px;")
        layout_g.addWidget(self.lbl_guia_archivo)

        layout_sel = QHBoxLayout()
        self.input_ruta = QLineEdit(self); self.input_ruta.setMinimumHeight(28)
        self.input_ruta.setPlaceholderText("Seleccionar archivo .csv o .xlsx con datos...")
        self.btn_examinar = QPushButton("Examinar...", self); self.btn_examinar.setMinimumHeight(28)
        self.btn_examinar.setToolTip("Buscar archivo .csv o Excel en el disco local.")
        conectar_boton_protegido(self.btn_examinar, self._abrir_dialogo_archivo, "[INFO] Seleccionando...", 500)
        layout_sel.addWidget(self.input_ruta, stretch=1); layout_sel.addWidget(self.btn_examinar)
        layout_g.addLayout(layout_sel)

        self.layout_hoja = QHBoxLayout()
        self.lbl_hoja = QLabel("Hoja de Excel:", self); self.lbl_hoja.setStyleSheet("font-weight: bold;")
        self.combo_hojas = QComboBox(self); self.combo_hojas.setMinimumHeight(28)
        self.combo_hojas.currentTextChanged.connect(self._al_cambiar_hoja)
        self.layout_hoja.addWidget(self.lbl_hoja); self.layout_hoja.addWidget(self.combo_hojas, stretch=1)
        self.lbl_hoja.setVisible(False); self.combo_hojas.setVisible(False)
        layout_g.addLayout(self.layout_hoja)

        layout_acciones = QHBoxLayout()
        self.lbl_guia_cols = QLabel("Columnas para evaluar con |:", self)
        layout_acciones.addWidget(self.lbl_guia_cols); layout_acciones.addStretch()
        self.btn_todas = QPushButton("Todas", self); self.btn_todas.setMinimumHeight(26); self.btn_todas.setMinimumWidth(75)
        self.btn_todas.setToolTip("Marcar todas las columnas del archivo.")
        conectar_boton_protegido(self.btn_todas, self._marcar_todas, "[INFO] Marcando todas las columnas...", tiempo_bloqueo_ms=300)
        self.btn_ninguna = QPushButton("Ninguna", self); self.btn_ninguna.setMinimumHeight(26); self.btn_ninguna.setMinimumWidth(85)
        self.btn_ninguna.setToolTip("Desmarcar todas las columnas.")
        conectar_boton_protegido(self.btn_ninguna, self._desmarcar_todas, "[INFO] Desmarcando todas las columnas...", tiempo_bloqueo_ms=300)
        layout_acciones.addWidget(self.btn_todas); layout_acciones.addWidget(self.btn_ninguna)
        layout_g.addLayout(layout_acciones)

        self.lista_columnas = QListWidget(self); self.lista_columnas.setMinimumHeight(75)
        self.lista_columnas.setMaximumHeight(350); self.lista_columnas.setFixedHeight(95)
        layout_g.addWidget(self.lista_columnas)
        layout_g.addWidget(TiradorRedimensionVertical(self.lista_columnas, 75, 350, parent=self))
        layout_principal.addWidget(grupo_archivo)

        # 2. Plantillas e Instrucciones
        grupo_prompt = QGroupBox("Plantillas IA Web e Instrucciones", self)
        layout_p = QVBoxLayout(grupo_prompt)
        layout_p.setContentsMargins(8, 8, 8, 8); layout_p.setSpacing(4)

        self.lbl_guia_prompt = QLabel("[INFO] 2. Instrucciones: Seleccione o escriba los criterios del sistema.", self)
        self.lbl_guia_prompt.setStyleSheet("color: #58615B; font-size: 11px;")
        layout_p.addWidget(self.lbl_guia_prompt)

        layout_combo = QHBoxLayout()
        layout_combo.addWidget(QLabel("Plantilla IA Web:", self))
        self.combo_plantillas = QComboBox(self)
        self.combo_plantillas.setToolTip("Cargar plantilla predefinida o redactar instrucciones libres.")
        self.combo_plantillas.currentIndexChanged.connect(self._al_seleccionar_plantilla)
        layout_combo.addWidget(self.combo_plantillas, stretch=1)
        self.btn_plantillas = QPushButton("Gestionar Plantillas (|)", self)
        self.btn_plantillas.setToolTip("Abrir catálogo de plantillas para editar o agregar nuevas")
        conectar_boton_protegido(
            self.btn_plantillas, self.plantillas_solicitadas.emit,
            "[INFO] Abriendo plantillas...", tiempo_bloqueo_ms=600,
        )
        layout_combo.addWidget(self.btn_plantillas)
        layout_p.addLayout(layout_combo)

        self.txt_instrucciones = EditorTextoExpandible(altura_inicial=120, placeholder="Instrucciones para Modo IA...", parent=self)
        self.txt_instrucciones.texto_cambiado.connect(self._al_cambiar_texto)
        layout_p.addWidget(self.txt_instrucciones)

        self.lbl_contador = EtiquetaContadorTokens(self)
        layout_p.addWidget(self.lbl_contador)

        self.lbl_guia_lotes = QLabel("[INFO] 3. Lotes: Filas enviadas por mensaje y número de lotes antes de renovar chat.", self)
        self.lbl_guia_lotes.setStyleSheet("color: #58615B; font-size: 11px;")
        layout_p.addWidget(self.lbl_guia_lotes)

        layout_lote = QHBoxLayout()
        layout_lote.addWidget(QLabel("Filas por lote:", self))
        self.spin_lote = QSpinBox(self); self.spin_lote.setRange(1, 50); self.spin_lote.setValue(5)
        self.spin_lote.setToolTip("Cantidad de filas concatenadas con '|' que se envían por cada mensaje.")
        layout_lote.addWidget(self.spin_lote); layout_lote.addSpacing(12)
        layout_lote.addWidget(QLabel("Lotes por chat:", self))
        self.spin_lotes_conv = QSpinBox(self); self.spin_lotes_conv.setRange(1, 50); self.spin_lotes_conv.setValue(5)
        self.spin_lotes_conv.setToolTip("Cantidad de lotes sucesivos antes de renovar conversación para mantener el contexto limpio.")
        layout_lote.addWidget(self.spin_lotes_conv); layout_lote.addStretch()
        layout_p.addLayout(layout_lote)
        layout_principal.addWidget(grupo_prompt)

    def _al_cambiar_texto(self) -> None:
        self.lbl_contador.actualizar(self.txt_instrucciones.toPlainText())

    def adaptar_modo(self, modo: ModoPantalla) -> None:
        """Adapta etiquetas descriptivas y textos al tamano de pantalla."""
        c = modo == ModoPantalla.COMPACTO
        self.lbl_guia_archivo.setText("[INFO] 1. Archivo CSV / Excel" if c else "[INFO] 1. Archivo: Seleccione el archivo CSV o Excel a clasificar.")
        self.lbl_guia_cols.setText("Cols con |:" if c else "Columnas para evaluar con |:")
        self.lbl_guia_prompt.setText("[INFO] 2. Instrucciones IA" if c else "[INFO] 2. Instrucciones: Seleccione o escriba los criterios del sistema.")
        self.lbl_guia_lotes.setText("[INFO] 3. Lotes" if c else "[INFO] 3. Lotes: Filas por mensaje y lotes antes de renovar chat.")
        self.btn_todas.setText("All" if c else "Todas")
        self.btn_ninguna.setText("None" if c else "Ninguna")
        self.lbl_contador.adaptar_modo(modo)

    def _abrir_dialogo_archivo(self) -> None:
        self._enrutador.datos.mkdir(parents=True, exist_ok=True)
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Archivo Tabular", str(self._enrutador.datos),
            "Archivos Tabulares (*.csv *.xlsx *.xlsm);;Archivos CSV (*.csv);;Archivos Excel (*.xlsx *.xlsm);;Todos (*.*)",
        )
        if ruta: self.cargar_archivo(Path(ruta))

    def cargar_archivo(self, ruta: Path) -> None:
        """Carga el archivo, detecta hojas de Excel y lee las columnas de forma ultra-ligera."""
        self._ruta_archivo = ruta; self.input_ruta.setText(str(ruta))
        hojas: list[str] = obtener_hojas_excel(ruta) if ruta.suffix.lower() in (".xlsx", ".xlsm") else []
        self.combo_hojas.blockSignals(True); self.combo_hojas.clear()
        if len(hojas) > 1:
            self.combo_hojas.addItems(hojas); self.lbl_hoja.setVisible(True); self.combo_hojas.setVisible(True)
            self.combo_hojas.blockSignals(False)
            self.log_notificado.emit(f"[INFO] Excel con {len(hojas)} hojas. Hoja activa: '{hojas[0]}'.")
            self._leer_columnas_de_hoja(ruta, hojas[0])
        else:
            self.lbl_hoja.setVisible(False); self.combo_hojas.setVisible(False); self.combo_hojas.blockSignals(False)
            self._leer_columnas_de_hoja(ruta, hojas[0] if hojas else None)

    def _al_cambiar_hoja(self, hoja: str) -> None:
        if self._ruta_archivo and hoja:
            self._leer_columnas_de_hoja(self._ruta_archivo, hoja)
            self.log_notificado.emit(f"[INFO] Hoja seleccionada: '{hoja}'. Columnas actualizadas.")

    def _leer_columnas_de_hoja(self, ruta: Path, nombre_hoja: str | None) -> None:
        self.lista_columnas.clear()
        try:
            lector = crear_lector_flujo(ruta, nombre_hoja_excel=nombre_hoja)
            encabezados = lector.inicializar(ruta)
            self._columnas = [h.strip() for h in encabezados if h.strip()]
            for col in self._columnas:
                item = QListWidgetItem(col)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                self.lista_columnas.addItem(item)
            hoja_txt = f" (hoja '{nombre_hoja}')" if nombre_hoja else ""
            self.log_notificado.emit(f"[OK] Archivo cargado: {ruta.name}{hoja_txt} con {len(self._columnas)} columnas")
        except Exception as error:
            self.log_notificado.emit(f"[ERROR] No se pudo leer columnas: {error}")

    def _marcar_todas(self) -> None:
        for i in range(self.lista_columnas.count()):
            self.lista_columnas.item(i).setCheckState(Qt.CheckState.Checked)

    def _desmarcar_todas(self) -> None:
        for i in range(self.lista_columnas.count()):
            self.lista_columnas.item(i).setCheckState(Qt.CheckState.Unchecked)

    def _cargar_plantillas(self) -> None:
        actual = self.combo_plantillas.currentData()
        self.combo_plantillas.clear()
        self.combo_plantillas.addItem("(Escribir prompt personalizado...)", "")
        if not self._servicio_prompts:
            return
        try:
            from procesos_ia.aplicacion.ia_web.comun.prompts_ia_web import asegurar_plantillas_ia_web
            asegurar_plantillas_ia_web(self._servicio_prompts)
            for p in self._servicio_prompts.listar_plantillas(categoria="ia_web"):
                self.combo_plantillas.addItem(p.titulo, p.identificador)
            if actual:
                idx = self.combo_plantillas.findData(actual)
                if idx >= 0:
                    self.combo_plantillas.setCurrentIndex(idx)
                    self._al_seleccionar_plantilla()
        except Exception:
            pass

    def _al_seleccionar_plantilla(self) -> None:
        c = self.combo_plantillas.currentData()
        if not c:
            self._al_cambiar_texto()
            return
        p = self._servicio_prompts.obtener_plantilla(str(c)) if self._servicio_prompts else None
        if p is not None:
            self.txt_instrucciones.setPlainText(p.contenido)
            self.log_notificado.emit(f"[INFO] Plantilla IA Web cargada: {p.titulo}")
        else:
            self.txt_instrucciones.setPlainText(str(c))
            self.log_notificado.emit(f"[INFO] Plantilla IA Web cargada: {self.combo_plantillas.currentText()}")
        self._al_cambiar_texto()

    def obtener_ruta_archivo(self) -> Path | None: return self._ruta_archivo
    def obtener_hoja_seleccionada(self) -> str | None:
        return self.combo_hojas.currentText().strip() or None if self.combo_hojas.isVisible() else None

    def obtener_columnas_seleccionadas(self) -> list[str]:
        return [self.lista_columnas.item(i).text() for i in range(self.lista_columnas.count())
                if self.lista_columnas.item(i).checkState() == Qt.CheckState.Checked]

    def obtener_instrucciones(self) -> str: return self.txt_instrucciones.toPlainText().strip()
    def obtener_tamano_lote(self) -> int: return self.spin_lote.value()
    def obtener_lotes_por_conversacion(self) -> int: return self.spin_lotes_conv.value()

    def obtener_parametros(self) -> dict[str, Any] | None:
        """Valida y estructura los parametros listos para HiloIAGeneral con la hoja seleccionada."""
        if not self._ruta_archivo or not self._ruta_archivo.exists(): return None
        hoja = self.obtener_hoja_seleccionada()
        filas = leer_filas_archivo_tabular(self._ruta_archivo, nombre_hoja=hoja)
        instr = self.obtener_instrucciones() or "Evalúa los registros según su información."
        if len(instr) > LIMITE_CARACTERES_MODO_IA:
            self.log_notificado.emit(f"[ALERTA] El prompt ({len(instr):,} car) supera el límite recomendado de {LIMITE_CARACTERES_MODO_IA:,}.")
        return {
            "filas": filas, "instrucciones": instr,
            "columnas": self.obtener_columnas_seleccionadas(),
            "tamano_lote": self.obtener_tamano_lote(),
            "lotes_por_conversacion": self.obtener_lotes_por_conversacion(),
            "nombre_salida": f"{self._ruta_archivo.stem}_{hoja}" if hoja else self._ruta_archivo.stem,
            "nombre_hoja": hoja,
        }

    def limpiar(self) -> None:
        """Restablece los campos del panel a su estado inicial."""
        self._ruta_archivo, self._columnas = None, []
        self.input_ruta.clear(); self.combo_hojas.clear()
        self.lbl_hoja.setVisible(False); self.combo_hojas.setVisible(False)
        self.lista_columnas.clear(); self.txt_instrucciones.clear()
        self.combo_plantillas.setCurrentIndex(0)
        self.spin_lote.setValue(5); self.spin_lotes_conv.setValue(5)
        self._al_cambiar_texto()
