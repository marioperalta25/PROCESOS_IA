"""Panel de interfaz especializada para Modo IA con imagenes 1 a 1 en chat."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.comun.gestor_lote_imagenes import (
    listar_imagenes_carpeta,
    verificar_estado_carpeta_imagenes,
)
from procesos_ia.interfaz.componentes.editor_texto_expandible import EditorTextoExpandible
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido
from procesos_ia.interfaz.responsivo import ModoPantalla


class PanelModoChatImagenes(QWidget):
    """Componente especializado para configurar extraccion de carpetas de imagenes en Modo IA."""

    log_notificado = Signal(str)

    def __init__(
        self,
        enrutador: EnrutadorSalidas | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._enrutador = enrutador or EnrutadorSalidas()
        self._carpeta_imagenes: Path | None = None
        self._carpeta_salida_custom: Path | None = None
        self._iniciar_ui()

    def _iniciar_ui(self) -> None:
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(6)

        # 1. Gestion de Carpeta de Imagenes
        grupo_carpeta = QGroupBox("Carpeta Local de Imágenes", self)
        layout_c = QVBoxLayout(grupo_carpeta)
        layout_c.setContentsMargins(8, 8, 8, 8); layout_c.setSpacing(4)

        self.lbl_guia_carpeta = QLabel("[INFO] 1. Carpeta: Seleccione el directorio que contiene las imágenes (.jpg, .png, .webp).", self)
        self.lbl_guia_carpeta.setStyleSheet("color: #58615B; font-size: 11px;")
        layout_c.addWidget(self.lbl_guia_carpeta)

        layout_sel = QHBoxLayout()
        self.input_carpeta = QLineEdit(self); self.input_carpeta.setMinimumHeight(28)
        self.input_carpeta.setPlaceholderText("Seleccionar carpeta con imágenes...")
        self.btn_examinar = QPushButton("Examinar Carpeta...", self); self.btn_examinar.setMinimumHeight(28)
        self.btn_examinar.setToolTip("Buscar directorio con imágenes en disco local.")
        conectar_boton_protegido(self.btn_examinar, self._abrir_dialogo_carpeta, "[INFO] Seleccionando...", 500)
        layout_sel.addWidget(self.input_carpeta, stretch=1); layout_sel.addWidget(self.btn_examinar)
        layout_c.addLayout(layout_sel)

        self.lbl_conteo = QLabel("Imágenes detectadas: 0", self)
        self.lbl_conteo.setStyleSheet("font-weight: bold; color: #1E293B;")
        layout_c.addWidget(self.lbl_conteo)
        layout_principal.addWidget(grupo_carpeta)

        # 2. Checkboxes de Campos Requeridos
        grupo_campos = QGroupBox("Campos de Extracción para la IA", self)
        layout_campos = QVBoxLayout(grupo_campos)
        layout_campos.setContentsMargins(8, 8, 8, 8); layout_campos.setSpacing(4)

        layout_botones_sel = QHBoxLayout()
        self.lbl_guia_campos = QLabel("Marque los datos que la IA debe extraer en cada imagen:", self)
        layout_botones_sel.addWidget(self.lbl_guia_campos); layout_botones_sel.addStretch()
        self.btn_todos = QPushButton("Todas", self); self.btn_todos.setMinimumHeight(24); self.btn_todos.setMinimumWidth(75)
        conectar_boton_protegido(self.btn_todos, self._marcar_todos, "[INFO] Marcando...", 300)
        self.btn_ninguno = QPushButton("Ninguna", self); self.btn_ninguno.setMinimumHeight(24); self.btn_ninguno.setMinimumWidth(85)
        conectar_boton_protegido(self.btn_ninguno, self._desmarcar_todos, "[INFO] Desmarcando...", 300)
        layout_botones_sel.addWidget(self.btn_todos); layout_botones_sel.addWidget(self.btn_ninguno)
        layout_campos.addLayout(layout_botones_sel)

        layout_checks = QHBoxLayout()
        self.chk_negocio = QCheckBox("Nombre del Negocio", self); self.chk_negocio.setChecked(True)
        self.chk_telefonos = QCheckBox("Teléfonos (con desglose)", self); self.chk_telefonos.setChecked(True)
        self.chk_owner = QCheckBox("Propietario / Owner", self); self.chk_owner.setChecked(True)
        self.chk_address = QCheckBox("Dirección / Address", self); self.chk_address.setChecked(True)
        self.chk_espanol = QCheckBox("Habla Espanol", self); self.chk_espanol.setChecked(True)

        layout_checks.addWidget(self.chk_negocio); layout_checks.addWidget(self.chk_telefonos)
        layout_checks.addWidget(self.chk_owner); layout_checks.addWidget(self.chk_address)
        layout_checks.addWidget(self.chk_espanol)
        layout_campos.addLayout(layout_checks)
        layout_principal.addWidget(grupo_campos)

        # 3. Criterios Adicionales y Rotacion
        grupo_params = QGroupBox("Instrucciones Adicionales y Rotación", self)
        layout_p = QVBoxLayout(grupo_params)
        layout_p.setContentsMargins(8, 8, 8, 8); layout_p.setSpacing(4)

        self.txt_instrucciones_extra = EditorTextoExpandible(
            altura_inicial=75, placeholder="Instrucciones o reglas específicas adicionales (opcional)...", parent=self
        )
        layout_p.addWidget(self.txt_instrucciones_extra)

        layout_rot = QHBoxLayout()
        layout_rot.addWidget(QLabel("Imágenes por conversación (máximo 3 recomendado):", self))
        self.spin_rotacion = QSpinBox(self); self.spin_rotacion.setRange(1, 10); self.spin_rotacion.setValue(3)
        self.spin_rotacion.setToolTip("Cantidad de imágenes enviadas antes de renovar conversación para limpiar contexto.")
        layout_rot.addWidget(self.spin_rotacion); layout_rot.addSpacing(16)

        self.input_salida = QLineEdit(self); self.input_salida.setPlaceholderText("Carpeta de salida predeterminada...")
        self.btn_examinar_salida = QPushButton("Destino CSV...", self); self.btn_examinar_salida.setMinimumHeight(26)
        conectar_boton_protegido(self.btn_examinar_salida, self._abrir_dialogo_salida, "[INFO] Destino...", 500)
        layout_rot.addWidget(self.input_salida, stretch=1); layout_rot.addWidget(self.btn_examinar_salida)
        layout_p.addLayout(layout_rot)
        layout_principal.addWidget(grupo_params)

    def _abrir_dialogo_carpeta(self) -> None:
        dir_base = self._enrutador.imagenes; dir_base.mkdir(parents=True, exist_ok=True)
        ruta = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Imágenes", str(dir_base))
        if ruta:
            self.cargar_carpeta(Path(ruta))

    def _abrir_dialogo_salida(self) -> None:
        dir_base = self._enrutador.modo_ia; dir_base.mkdir(parents=True, exist_ok=True)
        ruta = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Destino CSV", str(dir_base))
        if ruta:
            self._carpeta_salida_custom = Path(ruta)
            self.input_salida.setText(ruta)
            self.log_notificado.emit(f"[INFO] Carpeta de salida personalizada: {ruta}")

    def cargar_carpeta(self, ruta: Path) -> None:
        """Carga la carpeta y contabiliza las imagenes compatibles."""
        self._carpeta_imagenes = ruta
        self.input_carpeta.setText(str(ruta))
        dir_sal = self._carpeta_salida_custom or self._enrutador.modo_ia
        nombres_manif = None
        if hasattr(self._enrutador, "manifiesto_imagenes"):
            nombres_manif = self._enrutador.manifiesto_imagenes.obtener_procesadas(ruta.name)
        estado = verificar_estado_carpeta_imagenes(
            ruta, dir_sal, prefijo="modo_ia_imagenes", columna_fuente="archivo_imagen",
            nombres_manifiesto=nombres_manif,
        )
        if estado.imagenes_procesadas_count > 0:
            self.lbl_conteo.setText(
                f"Imágenes: {estado.total_imagenes} total ({estado.imagenes_procesadas_count} procesadas, {len(estado.imagenes_pendientes)} pendientes)"
            )
            self.log_notificado.emit(
                f"[INFO] Historial previo encontrado: {estado.imagenes_procesadas_count} procesadas, {len(estado.imagenes_pendientes)} pendientes."
            )
        else:
            self.lbl_conteo.setText(f"Imágenes detectadas: {estado.total_imagenes} (todas pendientes)")
            self.log_notificado.emit(f"[OK] Carpeta seleccionada: {ruta.name} ({estado.total_imagenes} imágenes detectadas)")

    def _marcar_todos(self) -> None:
        for chk in (self.chk_negocio, self.chk_telefonos, self.chk_owner, self.chk_address, self.chk_espanol):
            chk.setChecked(True)

    def _desmarcar_todos(self) -> None:
        for chk in (self.chk_negocio, self.chk_telefonos, self.chk_owner, self.chk_address, self.chk_espanol):
            chk.setChecked(False)

    def obtener_campos_activos(self) -> list[str]:
        """Recupera la lista de claves seleccionadas para el prompt."""
        campos: list[str] = []
        if self.chk_negocio.isChecked(): campos.append("negocio")
        if self.chk_telefonos.isChecked(): campos.append("telefonos")
        if self.chk_owner.isChecked(): campos.append("owner")
        if self.chk_address.isChecked(): campos.append("address")
        if self.chk_espanol.isChecked(): campos.append("habla_espanol")
        return campos

    def obtener_parametros(self) -> dict[str, Any] | None:
        """Valida y estructura los parametros para ejecucion."""
        if not self._carpeta_imagenes or not self._carpeta_imagenes.is_dir():
            return None
        campos = self.obtener_campos_activos()
        if not campos:
            campos = ["negocio", "telefonos"]
        return {
            "carpeta": self._carpeta_imagenes,
            "campos_activos": campos,
            "instrucciones_extra": self.txt_instrucciones_extra.toPlainText().strip(),
            "rotacion_chat": self.spin_rotacion.value(),
            "carpeta_salida": self._carpeta_salida_custom,
        }

    def adaptar_modo(self, modo: ModoPantalla) -> None:
        c = modo == ModoPantalla.COMPACTO
        self.lbl_guia_carpeta.setText("[INFO] 1. Carpeta" if c else "[INFO] 1. Carpeta: Seleccione el directorio que contiene las imágenes.")
        self.btn_todos.setText("All" if c else "Todas")
        self.btn_ninguno.setText("None" if c else "Ninguna")

    def limpiar(self) -> None:
        self._carpeta_imagenes = None
        self._carpeta_salida_custom = None
        self.input_carpeta.clear()
        self.input_salida.clear()
        self.lbl_conteo.setText("Imágenes detectadas: 0")
        self._marcar_todos()
        self.txt_instrucciones_extra.clear()
        self.spin_rotacion.setValue(3)

