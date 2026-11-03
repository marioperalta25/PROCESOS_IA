"""Vista interactiva para el modulo de IA General (Google Lens y Modo IA)."""

from __future__ import annotations

import os
from pathlib import Path
from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from procesos_ia.aplicacion.ia_web.comun.gestor_lote_imagenes import (
    listar_imagenes_carpeta, verificar_estado_carpeta_imagenes,
)
from procesos_ia.aplicacion.ia_web.visual_1a1.servicio_ia_general import ServicioIAGeneral
from procesos_ia.dominio.ia_web.desglosador_telefonos import desglosar_ficha_por_telefono
from procesos_ia.dominio.ia_web.ficha_negocio import FichaNegocioLens
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.interfaz.componentes.banner_notificacion import BannerNotificacion
from procesos_ia.interfaz.componentes.barra_navegacion import BarraNavegacionSubvista
from procesos_ia.interfaz.ia_web.componentes.barra_acciones_ia_general import BarraAccionesIAGeneral
from procesos_ia.interfaz.ia_web.componentes.consola_ia_general import ConsolaIAGeneral
from procesos_ia.interfaz.ia_web.componentes.panel_archivo_general import PanelArchivoGeneral
from procesos_ia.interfaz.ia_web.conversacional.medidor_tokens import LIMITE_CARACTERES_MODO_IA
from procesos_ia.interfaz.ia_web.conversacional.panel_modo_chat import PanelModoChat
from procesos_ia.interfaz.ia_web.hilos.hilo_ia_general import HiloIAGeneral
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido, liberar_boton_protegido
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
        enrutador: EnrutadorSalidas | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("IA General: Google Lens y Modo IA")
        self._config_web = configuracion_web or ConfiguracionWeb()
        self._gestor = gestor_sesion or GestorSesionNodriver(self._config_web)
        self._servicio = ServicioIAGeneral(self._gestor, self._config_web, enrutador=enrutador)
        self._servicio_prompts = servicio_prompts or self._crear_servicio_prompts()
        self._hilo: HiloIAGeneral | None = None
        self._carpeta_salida_custom: Path | None = None
        self._cancelando: bool = False

        self._iniciar_ui()
        self._actualizar_visibilidad()

    def _crear_servicio_prompts(self) -> object:
        from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
        from procesos_ia.infraestructura.prompts.repositorio_md import RepositorioPromptsMd; return ServicioCatalogoPrompts(RepositorioPromptsMd(self._servicio.enrutador.plantillas))

    def _iniciar_ui(self) -> None:
        from procesos_ia.interfaz.componentes.contenedor_responsivo import ContenedorPantallaResponsiva; from procesos_ia.interfaz.responsivo import configurar_tabla_responsiva
        layout_raiz = QVBoxLayout(self); layout_raiz.setContentsMargins(0, 0, 0, 0)
        self.contenedor = ContenedorPantallaResponsiva(self); layout_raiz.addWidget(self.contenedor)

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
        self.check_auditoria_md = QCheckBox("Generar auditoría (.md)", self)
        self.check_auditoria_md.setChecked(getattr(self._config_web, "generar_auditoria_md", True))
        self.check_auditoria_md.setToolTip("Activar o desactivar la creación del archivo Markdown (.md) de auditoría")
        layout_modo.addWidget(self.check_auditoria_md)
        self.contenedor.agregar_layout(layout_modo)
        self.lbl_guia_flujo = QLabel(self); self.lbl_guia_flujo.setWordWrap(True)
        self.lbl_guia_flujo.setStyleSheet("color: #58615B; font-size: 11px;")
        self.contenedor.agregar_widget(self.lbl_guia_flujo)

        # 2. Panel especializado para Modo Chat (sin selector de imagen)
        self.panel_modo_chat = PanelModoChat(self._servicio_prompts, self._servicio.enrutador, self)
        self.panel_modo_chat.log_notificado.connect(self._registrar_log)
        self.contenedor.agregar_widget(self.panel_modo_chat)

        # 3. Panel CSV y columnas para Google Lens
        self.panel_archivo = PanelArchivoGeneral(self, enrutador=self._servicio.enrutador)
        self.panel_archivo.log_notificado.connect(self._registrar_log)
        self.contenedor.agregar_widget(self.panel_archivo)

        # 4. Entrada alternativa para Lens (URL individual o Carpeta)
        self.grupo_alt = QGroupBox("Entrada Específica (URL / Carpeta)", self)
        layout_alt = QHBoxLayout(self.grupo_alt)
        self.input_alt = QLineEdit(self); self.btn_examinar_alt = QPushButton("Examinar...", self)
        conectar_boton_protegido(self.btn_examinar_alt, self._abrir_dialogo_alt, "[INFO]...", 500)
        layout_alt.addWidget(self.input_alt, stretch=1); layout_alt.addWidget(self.btn_examinar_alt)
        self.grupo_alt.setVisible(False); self.contenedor.agregar_widget(self.grupo_alt)

        # 5. Progreso y acciones
        self.barra_progreso = QProgressBar(self)
        self.barra_progreso.setRange(0, 100); self.barra_progreso.setValue(0)
        self.contenedor.agregar_widget(self.barra_progreso)

        self.barra_acciones = BarraAccionesIAGeneral(
            self._ejecutar_accion, self._cancelar_proceso,
            self._cambiar_carpeta_salida, self._abrir_carpeta_salida, self,
        )
        self.btn_ejecutar = self.barra_acciones.btn_ejecutar
        self.btn_cancelar = self.barra_acciones.btn_cancelar
        self.btn_destino = self.barra_acciones.btn_destino
        self.btn_abrir_salida = self.barra_acciones.btn_abrir_salida
        self.contenedor.agregar_widget(self.barra_acciones)

        # 6. Consola de bitacora y tabla
        self.consola = ConsolaIAGeneral(self); self.consola.setMinimumHeight(190)
        self.contenedor.agregar_widget(self.consola)
        self.tabla = QTableWidget(0, 7, self)
        self.tabla.setHorizontalHeaderLabels(["ID", "Estado IA", "Propietario", "Negocio", "Categoría", "Teléfono", "Ubicación"])
        self.tabla.setMinimumHeight(150); configurar_tabla_responsiva(self.tabla)
        self.contenedor.agregar_widget(self.tabla)

    def _actualizar_visibilidad(self) -> None:
        modo = self.combo_flujo.currentData()
        self.panel_modo_chat.setVisible(modo == "modo_ia")
        self.panel_archivo.setVisible(modo == "csv_lens")
        if modo == "csv_lens":
            self.panel_archivo.configurar_modo_imagen(True)
        self.grupo_alt.setVisible(modo in ("carpeta", "url"))
        self.btn_examinar_alt.setVisible(modo == "carpeta")

    def _abrir_dialogo_alt(self) -> None:
        dir_img = self._servicio.enrutador.imagenes; dir_img.mkdir(parents=True, exist_ok=True)
        ruta = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta", str(dir_img))
        if ruta: self.input_alt.setText(ruta); self._registrar_log(f"[INFO] Carpeta: {ruta}")

    def _ejecutar_accion(self) -> None:
        if self._hilo is not None and self._hilo.isRunning(): return
        modo, params, tipo = self.combo_flujo.currentData(), {}, ""
        if modo == "modo_ia":
            params_chat = self.panel_modo_chat.obtener_parametros()
            if not params_chat: self.banner.mostrar_error("[ERROR] Seleccione un archivo CSV o Excel válido."); return
            instr = params_chat.get("instrucciones", "")
            if len(instr) > LIMITE_CARACTERES_MODO_IA:
                self.banner.mostrar_error(f"[ERROR] El prompt ({len(instr):,} car) supera el límite de {LIMITE_CARACTERES_MODO_IA:,}. Redúzcalo.")
                return
            tipo, params = "modo_ia_lote", params_chat
        elif modo == "csv_lens":
            ruta_csv, col = self.panel_archivo.obtener_ruta_csv(), self.panel_archivo.obtener_columna_imagen()
            if not ruta_csv or not col:
                self.banner.mostrar_error("[ERROR] Seleccione el CSV y la columna de imagen."); return
            hoja = self.panel_archivo.obtener_hoja_seleccionada()
            tipo, params = "csv_imagenes", {"ruta_csv": ruta_csv, "columna": col, "nombre_hoja": hoja}
        elif modo == "carpeta":
            c = self.input_alt.text().strip().strip("\"'")
            if not c or not Path(c).is_dir():
                self.banner.mostrar_error("[ERROR] Seleccione una carpeta válida."); return
            p_carp = Path(c)
            rama = self._servicio.enrutador.gestor_procesos(self._carpeta_salida_custom).rama("imagenes")
            estado = verificar_estado_carpeta_imagenes(p_carp, rama, "extraccion_lens")
            if not estado.csv_existente:
                anterior = self._carpeta_salida_custom or self._servicio.enrutador.extracciones
                estado = verificar_estado_carpeta_imagenes(p_carp, anterior, "extraccion_lens")
            if estado.total_imagenes == 0:
                self.banner.mostrar_error("[ERROR] La carpeta seleccionada no contiene imágenes compatibles."); return

            if estado.csv_existente and not estado.hay_nuevas:
                box = QMessageBox(self); box.setWindowTitle("Carpeta al día")
                box.setText(f"No hay imágenes nuevas.\n\nCarpeta: {p_carp.resolve()}\nCSV: {estado.csv_existente.resolve()}")
                reprocesar = box.addButton("Reprocesar todo desde cero", QMessageBox.ButtonRole.DestructiveRole)
                box.addButton("Aceptar", QMessageBox.ButtonRole.AcceptRole); box.exec()
                if box.clickedButton() != reprocesar:
                    return
                estado.imagenes_pendientes = listar_imagenes_carpeta(p_carp)
                estado.csv_existente = None

            tipo, params = "carpeta_imagenes", {
                "carpeta": p_carp, "archivos": estado.imagenes_pendientes,
                "modo_escritura": "reanudar" if estado.csv_existente else "sobrescribir",
                "csv_existente": estado.csv_existente,
            }
        elif modo == "url":
            u = self.input_alt.text().strip()
            if not u:
                self.banner.mostrar_error("[ERROR] Ingrese una URL de imagen válida."); return
            tipo, params = "imagen_individual", {"fuente": u, "id_registro": "url_individual"}

        if self._carpeta_salida_custom:
            params["carpeta_salida"] = self._carpeta_salida_custom
        params["generar_auditoria_md"] = self.check_auditoria_md.isChecked()

        self._cancelando = False
        self.btn_ejecutar.setEnabled(False)
        self.btn_cancelar.setText("Detener")
        liberar_boton_protegido(self.btn_cancelar, habilitar=True)
        self.barra_progreso.setValue(0); self.banner.mostrar_en_proceso("[INFO] Ejecutando tarea en navegador compartido...")
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
        fue_cancelado = self._cancelando
        self._cancelando = False
        self.btn_ejecutar.setEnabled(True)
        self.btn_cancelar.setText("Detener")
        liberar_boton_protegido(self.btn_cancelar, habilitar=False)
        if fue_cancelado:
            self.barra_progreso.setValue(0)
            self.banner.mostrar_info("[INFO] Tarea cancelada por el usuario.")
            self._registrar_log("[INFO] Tarea cancelada por el usuario.")
        else:
            self.barra_progreso.setValue(100); self.banner.mostrar_exito(mensaje); self._registrar_log(mensaje)
        if isinstance(resultado, FichaNegocioLens):
            self._agregar_fila_tabla(resultado)
        elif isinstance(resultado, list):
            for item in resultado:
                if isinstance(item, FichaNegocioLens): self._agregar_fila_tabla(item)

    def _al_error(self, error: str) -> None:
        self._cancelando = False
        self.btn_ejecutar.setEnabled(True)
        self.btn_cancelar.setText("Detener")
        liberar_boton_protegido(self.btn_cancelar, habilitar=False)
        self.banner.mostrar_error(f"[ERROR] {error}"); self._registrar_log(f"[ERROR] {error}")

    def _cancelar_proceso(self) -> None:
        if self._cancelando:
            return
        self._cancelando = True
        self.btn_cancelar.setEnabled(False)
        self.btn_cancelar.setText("Cancelando...")
        self.banner.mostrar_en_proceso("[INFO] Cancelando tarea en curso...")
        if self._hilo is not None and self._hilo.isRunning():
            self._hilo.cancelar(); self._registrar_log("[INFO] Cancelando tarea en curso...")

    def _registrar_log(self, mensaje: str) -> None: self.consola.agregar_log(mensaje)

    def _agregar_fila_tabla(self, f: FichaNegocioLens) -> None:
        for item in desglosar_ficha_por_telefono(f):
            row = self.tabla.rowCount(); self.tabla.insertRow(row)
            for col, val in enumerate((item.id_registro, item.estado_ia, item.propietario, item.negocio, item.categoria, item.telefono, item.ubicacion)):
                self.tabla.setItem(row, col, QTableWidgetItem(val))

    def _cambiar_carpeta_salida(self) -> None:
        defecto = str(self._carpeta_salida_custom or self._servicio.enrutador.extracciones)
        ruta = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Destino", defecto)
        if ruta: self._carpeta_salida_custom = Path(ruta); self._registrar_log(f"[INFO] Destino: {ruta}")

    def _abrir_carpeta_salida(self) -> None:
        salidas = (self._servicio.ultima_salida.parent if self._servicio.ultima_salida
                   else (self._carpeta_salida_custom or self._servicio.enrutador.extracciones))
        salidas.mkdir(parents=True, exist_ok=True); os.startfile(str(salidas))

    def _limpiar_formulario(self) -> None:
        self.panel_modo_chat.limpiar(); self.panel_archivo.limpiar(); self.input_alt.clear()
        self.tabla.setRowCount(0); self.barra_progreso.setValue(0); self.consola.limpiar()
        self.banner.mostrar_info("[INFO] Formulario restablecido.")

    def _al_volver(self) -> None: self.volver_solicitado.emit()

    def adaptar_modo(self, modo: ModoPantalla) -> None:
        self.barra_acciones.adaptar_modo(modo)
        c = modo == ModoPantalla.COMPACTO
        if hasattr(self, "lbl_guia_flujo"):
            self.lbl_guia_flujo.setText(
                "[INFO] Modo IA: Lotes | Lens: Imágenes" if c
                else "[INFO OPERACIÓN] Selecciona Modo IA para evaluar texto por lotes, o Google Lens para extracción visual."
            )

    @property
    def combo_plantillas(self) -> QComboBox: return self.panel_modo_chat.combo_plantillas

    @property
    def txt_instrucciones(self) -> object: return self.panel_modo_chat.txt_instrucciones

    @property
    def spin_lote(self) -> QSpinBox: return self.panel_modo_chat.spin_lote
