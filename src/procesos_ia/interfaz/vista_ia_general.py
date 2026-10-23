"""Vista interactiva para el modulo de IA General (Google Lens y Modo IA)."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QProgressBar, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
)

from procesos_ia.aplicacion.servicio_ia_general import ServicioIAGeneral
from procesos_ia.dominio.ficha_negocio import FichaNegocioLens
from procesos_ia.infraestructura.web.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.interfaz.componentes.banner_notificacion import BannerNotificacion
from procesos_ia.interfaz.componentes.barra_navegacion import BarraNavegacionSubvista
from procesos_ia.interfaz.componentes.consola_ia_general import ConsolaIAGeneral
from procesos_ia.interfaz.componentes.panel_archivo_general import PanelArchivoGeneral
from procesos_ia.interfaz.hilo_ia_general import HiloIAGeneral
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido
from procesos_ia.interfaz.responsivo import ModoPantalla


class VistaIAGeneral(QWidget):
    """Panel de operacion para extracciones visuales en Google Lens y Modo IA."""

    volver_solicitado = Signal()

    def __init__(
        self,
        gestor_sesion: GestorSesionNodriver | None = None,
        configuracion_web: ConfiguracionWeb | None = None,
        servicio_prompts: object | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("IA General: Google Lens y Modo IA")
        self._config_web = configuracion_web or ConfiguracionWeb()
        self._gestor = gestor_sesion or GestorSesionNodriver(self._config_web)
        self._servicio = ServicioIAGeneral(self._gestor, self._config_web)
        self._servicio_prompts = servicio_prompts or self._crear_servicio_prompts()
        self._hilo: HiloIAGeneral | None = None

        self._iniciar_ui()
        self._cargar_plantillas_ia_web()

    def _crear_servicio_prompts(self) -> object:
        from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
        from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
        from procesos_ia.infraestructura.prompts.repositorio_md import RepositorioPromptsMd
        return ServicioCatalogoPrompts(RepositorioPromptsMd(EnrutadorSalidas().plantillas))

    def _iniciar_ui(self) -> None:
        from procesos_ia.interfaz.componentes.contenedor_responsivo import ContenedorPantallaResponsiva
        from procesos_ia.interfaz.responsivo import configurar_tabla_responsiva

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        self.contenedor = ContenedorPantallaResponsiva(self)
        layout_raiz.addWidget(self.contenedor)

        self.barra_nav = BarraNavegacionSubvista("Módulo IA General (Google Lens / Modo IA)", "Limpiar", self)
        self.barra_nav.volver_solicitado.connect(self._al_volver)
        self.barra_nav.limpiar_solicitado.connect(self._limpiar_formulario)
        self.contenedor.agregar_widget(self.barra_nav)
        self.banner = BannerNotificacion(self); self.contenedor.agregar_widget(self.banner)

        # 1. Selector de flujo
        layout_modo = QHBoxLayout()
        layout_modo.addWidget(QLabel("Operación:", self))
        self.combo_flujo = QComboBox(self)
        self.combo_flujo.addItem("Modo IA de Google (Prompt y Lotes CSV con |)", "modo_ia")
        self.combo_flujo.addItem("Google Lens con CSV de Imágenes / URLs", "csv_lens")
        self.combo_flujo.addItem("Google Lens con Carpeta de Imágenes (1 a 1)", "carpeta")
        self.combo_flujo.addItem("Google Lens con URL de Imagen Individual", "url")
        self.combo_flujo.currentIndexChanged.connect(self._actualizar_visibilidad)
        layout_modo.addWidget(self.combo_flujo, stretch=1)
        self.contenedor.agregar_layout(layout_modo)

        # 2. Panel CSV y columnas
        self.panel_archivo = PanelArchivoGeneral(self)
        self.panel_archivo.log_notificado.connect(self._registrar_log)
        self.contenedor.agregar_widget(self.panel_archivo)

        # 3. Entrada alternativa
        self.grupo_alt = QGroupBox("Entrada Específica (URL / Carpeta)", self)
        layout_alt = QHBoxLayout(self.grupo_alt)
        self.input_alt = QLineEdit(self)
        self.btn_examinar_alt = QPushButton("Examinar...", self)
        conectar_boton_protegido(self.btn_examinar_alt, self._abrir_dialogo_alt, "[INFO]...", 500)
        layout_alt.addWidget(self.input_alt, stretch=1); layout_alt.addWidget(self.btn_examinar_alt)
        self.grupo_alt.setVisible(False); self.contenedor.agregar_widget(self.grupo_alt)

        # 4. Prompt y plantillas
        self.grupo_prompt = QGroupBox("Plantillas IA Web e Instrucciones", self)
        layout_p = QVBoxLayout(self.grupo_prompt)
        layout_pl = QHBoxLayout()
        layout_pl.addWidget(QLabel("Plantilla IA Web:", self))
        self.combo_plantillas = QComboBox(self)
        self.combo_plantillas.currentIndexChanged.connect(self._al_seleccionar_plantilla)
        layout_pl.addWidget(self.combo_plantillas, stretch=1)
        layout_p.addLayout(layout_pl)

        from procesos_ia.interfaz.componentes.editor_texto_expandible import EditorTextoExpandible
        self.txt_instrucciones = EditorTextoExpandible(
            altura_inicial=120, placeholder="Instrucciones para Modo IA...", parent=self,
        )
        layout_p.addWidget(self.txt_instrucciones)

        layout_lote = QHBoxLayout()
        layout_lote.addWidget(QLabel("Filas por lote:", self))
        self.spin_lote = QSpinBox(self)
        self.spin_lote.setRange(1, 50); self.spin_lote.setValue(5)
        layout_lote.addWidget(self.spin_lote); layout_lote.addStretch()
        layout_p.addLayout(layout_lote); self.contenedor.agregar_widget(self.grupo_prompt)

        # 5. Progreso y acciones
        self.barra_progreso = QProgressBar(self)
        self.barra_progreso.setRange(0, 100); self.barra_progreso.setValue(0)
        self.contenedor.agregar_widget(self.barra_progreso)

        layout_botones = QHBoxLayout()
        self.btn_ejecutar = QPushButton("Iniciar Proceso en Navegador Compartido", self)
        self.btn_ejecutar.setMinimumHeight(32)
        conectar_boton_protegido(self.btn_ejecutar, self._ejecutar_accion, "[INFO] Iniciando...", 800)
        layout_botones.addWidget(self.btn_ejecutar, stretch=2)
        self.btn_cancelar = QPushButton("Detener", self); self.btn_cancelar.setEnabled(False)
        conectar_boton_protegido(self.btn_cancelar, self._cancelar_proceso, tiempo_bloqueo_ms=1000)
        layout_botones.addWidget(self.btn_cancelar, stretch=1)
        self.btn_abrir_salida = QPushButton("Abrir Carpeta de Salida", self)
        conectar_boton_protegido(self.btn_abrir_salida, self._abrir_carpeta_salida, tiempo_bloqueo_ms=800)
        layout_botones.addWidget(self.btn_abrir_salida, stretch=1)
        self.contenedor.agregar_layout(layout_botones)

        # 6. Consola de bitacora abajo y tabla con altura garantizada
        self.consola = ConsolaIAGeneral(self); self.consola.setMinimumHeight(190)
        self.contenedor.agregar_widget(self.consola)
        self.tabla = QTableWidget(0, 7, self)
        self.tabla.setHorizontalHeaderLabels(["ID", "Estado IA", "Propietario", "Negocio", "Categoría", "Teléfono", "Ubicación"])
        self.tabla.setMinimumHeight(150)
        configurar_tabla_responsiva(self.tabla)
        self.contenedor.agregar_widget(self.tabla)

    def _cargar_plantillas_ia_web(self) -> None:
        self.combo_plantillas.clear()
        self.combo_plantillas.addItem("(Escribir prompt personalizado...)", "")
        try:
            from procesos_ia.aplicacion.prompts_ia_web import asegurar_plantillas_ia_web
            asegurar_plantillas_ia_web(self._servicio_prompts)
            for p in self._servicio_prompts.listar_plantillas(categoria="ia_web"):
                self.combo_plantillas.addItem(f"{p.titulo}", p.contenido)
        except Exception:
            pass

    def _al_seleccionar_plantilla(self) -> None:
        contenido = self.combo_plantillas.currentData()
        if contenido:
            self.txt_instrucciones.setPlainText(str(contenido))
            self._registrar_log(f"[INFO] Plantilla IA Web cargada: {self.combo_plantillas.currentText()}")

    def _actualizar_visibilidad(self) -> None:
        modo = self.combo_flujo.currentData()
        es_csv = modo in ("modo_ia", "csv_lens")
        self.panel_archivo.setVisible(es_csv)
        self.grupo_alt.setVisible(not es_csv)
        self.grupo_prompt.setVisible(modo == "modo_ia")
        self.btn_examinar_alt.setVisible(modo == "carpeta")

    def _abrir_dialogo_alt(self) -> None:
        dir_img = self._servicio._enrutador.imagenes
        dir_img.mkdir(parents=True, exist_ok=True)
        ruta = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta", str(dir_img))
        if ruta:
            self.input_alt.setText(ruta)
            self._registrar_log(f"[INFO] Carpeta seleccionada: {ruta}")

    def _ejecutar_accion(self) -> None:
        if self._hilo is not None and self._hilo.isRunning(): return
        modo, params, tipo = self.combo_flujo.currentData(), {}, ""
        if modo == "modo_ia":
            ruta_csv = self.panel_archivo.obtener_ruta_csv()
            if not ruta_csv or not ruta_csv.exists():
                self.banner.mostrar_error("[ERROR] Seleccione un archivo CSV válido."); return
            with open(ruta_csv, mode="r", encoding="utf-8-sig", errors="ignore") as f:
                filas = list(csv.DictReader(f))
            tipo, params = "modo_ia_lote", {
                "filas": filas, "instrucciones": self.txt_instrucciones.toPlainText().strip() or "Evalúa los registros.",
                "columnas": self.panel_archivo.obtener_columnas_seleccionadas(),
                "tamano_lote": self.spin_lote.value(), "nombre_salida": ruta_csv.stem,
            }
        elif modo == "csv_lens":
            ruta_csv, col = self.panel_archivo.obtener_ruta_csv(), self.panel_archivo.obtener_columna_imagen()
            if not ruta_csv or not col:
                self.banner.mostrar_error("[ERROR] Seleccione el CSV y la columna de imagen."); return
            tipo, params = "csv_imagenes", {"ruta_csv": ruta_csv, "columna": col}
        elif modo == "carpeta":
            c = self.input_alt.text().strip()
            if not c or not Path(c).is_dir():
                self.banner.mostrar_error("[ERROR] Seleccione una carpeta válida."); return
            tipo, params = "carpeta_imagenes", {"carpeta": c}
        else:
            u = self.input_alt.text().strip()
            if not u:
                self.banner.mostrar_error("[ERROR] Ingrese una URL de imagen."); return
            tipo, params = "imagen_individual", {"fuente": u, "id_registro": "img_1"}

        self.btn_ejecutar.setEnabled(False); self.btn_cancelar.setEnabled(True)
        self.barra_progreso.setValue(0)
        self.banner.mostrar_en_proceso("[INFO] Ejecutando tarea en navegador compartido...")
        self._hilo = HiloIAGeneral(self._servicio, tipo, params, self)
        self._hilo.progreso_actualizado.connect(self._al_progreso)
        self._hilo.senial_log.connect(self._registrar_log)
        self._hilo.proceso_completado.connect(self._al_exito)
        self._hilo.proceso_fallido.connect(self._al_error)
        self._hilo.start()

    def _al_progreso(self, actual: int, total: int, detalle: str) -> None:
        pct = int((actual / total) * 100) if total > 0 else 0
        self.barra_progreso.setValue(pct)
        self.banner.mostrar_en_proceso(f"[EN PROCESO] ({actual}/{total}) {detalle}")

    def _al_exito(self, mensaje: str, resultado: object) -> None:
        self.btn_ejecutar.setEnabled(True); self.btn_cancelar.setEnabled(False)
        self.barra_progreso.setValue(100)
        self.banner.mostrar_exito(mensaje); self._registrar_log(mensaje)
        if isinstance(resultado, FichaNegocioLens):
            self._agregar_fila_tabla(resultado)
        elif isinstance(resultado, list):
            for item in resultado:
                if isinstance(item, FichaNegocioLens):
                    self._agregar_fila_tabla(item)

    def _al_error(self, error: str) -> None:
        self.btn_ejecutar.setEnabled(True); self.btn_cancelar.setEnabled(False)
        self.banner.mostrar_error(f"[ERROR] {error}"); self._registrar_log(f"[ERROR] {error}")

    def _cancelar_proceso(self) -> None:
        self.btn_cancelar.setEnabled(False)
        if self._hilo is not None and self._hilo.isRunning():
            self._hilo.cancelar(); self._registrar_log("[INFO] Cancelando tarea en curso...")

    def _registrar_log(self, mensaje: str) -> None: self.consola.agregar_log(mensaje)

    def _agregar_fila_tabla(self, f: FichaNegocioLens) -> None:
        row = self.tabla.rowCount()
        self.tabla.insertRow(row)
        for col, val in enumerate((f.id_registro, f.estado_ia, f.propietario, f.negocio, f.categoria, f.telefono, f.ubicacion)):
            self.tabla.setItem(row, col, QTableWidgetItem(val))

    def _abrir_carpeta_salida(self) -> None:
        salidas = self._servicio._enrutador.extracciones
        salidas.mkdir(parents=True, exist_ok=True); os.startfile(str(salidas))

    def _limpiar_formulario(self) -> None:
        self.txt_instrucciones.clear(); self.input_alt.clear()
        self.tabla.setRowCount(0); self.barra_progreso.setValue(0)
        self.consola.limpiar(); self.banner.mostrar_info("[INFO] Formulario restablecido.")

    def _al_volver(self) -> None: self.volver_solicitado.emit()

    def adaptar_modo(self, modo: ModoPantalla) -> None:
        txt = "Iniciar" if modo == ModoPantalla.COMPACTO else "Iniciar Proceso en Navegador Compartido"
        self.btn_ejecutar.setText(txt)
