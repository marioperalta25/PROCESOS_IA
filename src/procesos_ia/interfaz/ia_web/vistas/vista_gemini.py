"""Vista interactiva y dedicada para el modulo de Google Gemini Web."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
    QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.comun.gestor_checkpoint_imagenes import GestorCheckpointImagenes
from procesos_ia.interfaz.comun.dialogo_checkpoint_imagenes import (
    solicitar_decision_checkpoint_imagenes,
)
from procesos_ia.aplicacion.ia_web.comun.gestor_lote_imagenes import (
    listar_imagenes_carpeta,
)
from procesos_ia.interfaz.comun.preparacion_tabular import preparar_trabajo_con_dialogo
from procesos_ia.aplicacion.ia_web.visual_1a1.procesador_archivo_urls import leer_filas_archivo_tabular
from procesos_ia.aplicacion.ia_web.motores.servicio_procesamiento_web import ServicioProcesamientoWeb
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb, PERFIL_GEMINI
from procesos_ia.interfaz.componentes.banner_notificacion import BannerNotificacion
from procesos_ia.interfaz.componentes.barra_navegacion import BarraNavegacionSubvista
from procesos_ia.interfaz.componentes.contenedor_responsivo import ContenedorPantallaResponsiva
from procesos_ia.interfaz.componentes.editor_texto_expandible import EditorTextoExpandible
from procesos_ia.interfaz.ia_web.componentes.consola_ia_general import ConsolaIAGeneral
from procesos_ia.interfaz.ia_web.componentes.panel_archivo_general import PanelArchivoGeneral
from procesos_ia.interfaz.ia_web.conversacional.panel_modo_chat_imagenes import PanelModoChatImagenes
from procesos_ia.interfaz.ia_web.hilos.hilo_navegador import HiloLanzarNavegador
from procesos_ia.interfaz.ia_web.hilos.hilo_procesamiento_web import HiloProcesamientoWeb
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido, liberar_boton_protegido
from procesos_ia.interfaz.responsivo import ModoPantalla


class VistaGemini(QWidget):
    """Panel operativo interactivo para procesamiento por lotes e imagenes con Gemini Web."""

    volver_solicitado = Signal()
    deepseek_solicitado = Signal()
    ia_general_solicitado = Signal()
    plantillas_solicitadas = Signal()

    def __init__(
        self,
        configuracion_web: ConfiguracionWeb | None = None,
        servicio_prompts: object | None = None,
        enrutador: EnrutadorSalidas | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("IA Web: Google Gemini (gemini.google.com)")
        self._config_web = configuracion_web or ConfiguracionWeb(nombre_perfil=PERFIL_GEMINI)
        self._servicio_prompts = servicio_prompts
        self._enrutador = enrutador or EnrutadorSalidas()
        self._servicio_proc = ServicioProcesamientoWeb(configuracion_web=self._config_web, enrutador=self._enrutador)
        self._hilo_nav: HiloLanzarNavegador | None = None
        self._hilo_proc: HiloProcesamientoWeb | None = None
        self._ultima_salida: Path | None = None

        self._iniciar_ui()
        self._cargar_plantillas()

    def _iniciar_ui(self) -> None:
        layout_raiz = QVBoxLayout(self); layout_raiz.setContentsMargins(0, 0, 0, 0)
        self.contenedor = ContenedorPantallaResponsiva(self); layout_raiz.addWidget(self.contenedor)

        self.barra_nav = BarraNavegacionSubvista("Módulo Google Gemini Web (gemini.google.com)", "Limpiar", self)
        self.barra_nav.volver_solicitado.connect(self._al_volver); self.barra_nav.limpiar_solicitado.connect(self._limpiar_formulario)
        self.contenedor.agregar_widget(self.barra_nav)

        self.banner = BannerNotificacion(self)
        self.banner.mostrar_info("[INFO] Google Gemini Web: Procesamiento por lotes tabulares con '|' o imágenes 1 a 1.")
        self.contenedor.agregar_widget(self.banner)

        grupo_sesion = QGroupBox("Navegador Gemini", self); lay_s = QHBoxLayout(grupo_sesion)
        self.btn_iniciar_sesion = QPushButton("Iniciar Sesión / Abrir Gemini", self)
        conectar_boton_protegido(self.btn_iniciar_sesion, self._abrir_navegador_manual, "[INFO] Abriendo Gemini...", 800)
        self.btn_limpiar_bloqueos = QPushButton("Limpiar Bloqueos de Perfil", self)
        conectar_boton_protegido(self.btn_limpiar_bloqueos, self._limpiar_bloqueos, "[INFO] Limpiando bloqueos...", 600)
        lay_s.addWidget(self.btn_iniciar_sesion, stretch=2); lay_s.addWidget(self.btn_limpiar_bloqueos, stretch=1)
        self.contenedor.agregar_widget(grupo_sesion)

        lay_op = QHBoxLayout(); lay_op.addWidget(QLabel("Operación Gemini:", self))
        self.combo_operacion = QComboBox(self)
        self.combo_operacion.addItem("Procesamiento por Lotes de Texto en Gemini (CSV con delimitador '|') ", "csv_texto")
        self.combo_operacion.addItem("Extracción de Imágenes en Gemini (1 a 1 - Carpeta con campos estructurados)", "extraccion_negocios_imagenes")
        self.combo_operacion.currentIndexChanged.connect(self._al_cambiar_operacion)
        self.check_auditoria_md = QCheckBox("Generar auditoría (.md)", self)
        self.check_auditoria_md.setChecked(getattr(self._config_web, "generar_auditoria_md", True))
        lay_op.addWidget(self.combo_operacion, stretch=1); lay_op.addWidget(self.check_auditoria_md)
        self.contenedor.agregar_layout(lay_op)

        self.panel_imagenes_1a1 = PanelModoChatImagenes(self._enrutador, self, nombre_modulo="Google Gemini Web")
        self.panel_imagenes_1a1.log_notificado.connect(self.consola_log_puente)
        self.panel_imagenes_1a1.setVisible(False); self.contenedor.agregar_widget(self.panel_imagenes_1a1)

        self.panel_archivo = PanelArchivoGeneral(self, enrutador=self._enrutador, nombre_modulo="Google Gemini Web")
        self.contenedor.agregar_widget(self.panel_archivo)

        self.grupo_prompt = QGroupBox("Instrucciones de Evaluación para Gemini (Prompt)", self)
        lay_p = QVBoxLayout(self.grupo_prompt); lay_top = QHBoxLayout()
        lay_top.addWidget(QLabel("Plantilla para Gemini:", self))
        self.combo_plantillas = QComboBox(self); self.combo_plantillas.currentIndexChanged.connect(self._al_seleccionar_plantilla)
        self.btn_plantillas = QPushButton("Gestionar Plantillas (|)", self)
        conectar_boton_protegido(self.btn_plantillas, self.plantillas_solicitadas.emit, "[INFO] Abriendo plantillas...", 600)
        lay_top.addWidget(self.combo_plantillas, stretch=1); lay_top.addWidget(self.btn_plantillas); lay_p.addLayout(lay_top)
        self.txt_instrucciones = EditorTextoExpandible(placeholder="Instrucciones y criterios de evaluación para Google Gemini...", parent=self)
        lay_p.addWidget(self.txt_instrucciones); self.contenedor.agregar_widget(self.grupo_prompt)

        self.grupo_lotes = QGroupBox("Configuración de Lotes y Rotación (Gemini)", self)
        lay_l = QHBoxLayout(self.grupo_lotes)
        self.spin_lote = QSpinBox(self); self.spin_lote.setRange(1, 50); self.spin_lote.setValue(5)
        self.spin_rotacion = QSpinBox(self); self.spin_rotacion.setRange(1, 50); self.spin_rotacion.setValue(2)
        lay_l.addWidget(QLabel("Filas por lote (Gemini):", self)); lay_l.addWidget(self.spin_lote); lay_l.addSpacing(16)
        lay_l.addWidget(QLabel("Rotar chat Gemini cada (lotes):", self)); lay_l.addWidget(self.spin_rotacion); lay_l.addStretch()
        self.contenedor.agregar_widget(self.grupo_lotes)

        # 7. Barra de Progreso y Consola
        self.barra_progreso = QProgressBar(self); self.barra_progreso.setRange(0, 100); self.barra_progreso.setValue(0)
        self.contenedor.agregar_widget(self.barra_progreso)
        self.consola = ConsolaIAGeneral(self); self.consola.setMinimumHeight(170)
        self.panel_archivo.log_notificado.connect(self.consola.agregar_log)

        lay_btns = QHBoxLayout()
        self.btn_ejecutar = QPushButton("Iniciar Procesamiento en Gemini", self); self.btn_ejecutar.setMinimumHeight(32)
        conectar_boton_protegido(self.btn_ejecutar, self._ejecutar_procesamiento, "[INFO] Iniciando Gemini...", auto_desbloquear=False)
        self.btn_cancelar = QPushButton("Detener Gemini", self); self.btn_cancelar.setEnabled(False)
        conectar_boton_protegido(self.btn_cancelar, self._cancelar_procesamiento, tiempo_bloqueo_ms=0, auto_desbloquear=False)
        self.btn_abrir_salida = QPushButton("Abrir Salida Gemini", self)
        conectar_boton_protegido(self.btn_abrir_salida, self._abrir_carpeta_salida, tiempo_bloqueo_ms=800)
        self.btn_ir_deepseek = QPushButton("Ir a DeepSeek Web", self)
        conectar_boton_protegido(self.btn_ir_deepseek, self.deepseek_solicitado.emit, tiempo_bloqueo_ms=800)
        self.btn_ir_ia_general = QPushButton("Ir a IA General (Lens / Modo IA)", self)
        conectar_boton_protegido(self.btn_ir_ia_general, self.ia_general_solicitado.emit, tiempo_bloqueo_ms=800)
        for b, s in ((self.btn_ejecutar, 2), (self.btn_cancelar, 1), (self.btn_abrir_salida, 1),
                     (self.btn_ir_deepseek, 1), (self.btn_ir_ia_general, 1)):
            lay_btns.addWidget(b, stretch=s)
        self.contenedor.agregar_layout(lay_btns); self.contenedor.agregar_widget(self.consola)

    def consola_log_puente(self, msg: str) -> None:
        if hasattr(self, "consola"): self.consola.agregar_log(msg)

    def _al_cambiar_operacion(self) -> None:
        es_img = self.combo_operacion.currentData() == "extraccion_negocios_imagenes"
        self.panel_imagenes_1a1.setVisible(es_img); self.panel_archivo.setVisible(not es_img)
        self.grupo_prompt.setVisible(not es_img); self.grupo_lotes.setVisible(not es_img)

    def _abrir_navegador_manual(self) -> None:
        self.consola.agregar_log("[INFO] Abriendo Chromium en Gemini Web...")
        self.btn_iniciar_sesion.setEnabled(False)
        self._hilo_nav = HiloLanzarNavegador(url_destino=self._config_web.url_gemini, configuracion=self._config_web, parent=self)
        self._hilo_nav.senial_exito.connect(lambda m: (liberar_boton_protegido(self.btn_iniciar_sesion), self.consola.agregar_log(f"[OK] {m}")))
        self._hilo_nav.senial_error.connect(lambda m: (liberar_boton_protegido(self.btn_iniciar_sesion), self.consola.agregar_log(f"[ERROR] {m}")))
        self._hilo_nav.start()

    def _limpiar_bloqueos(self) -> None:
        self._config_web.limpiar_bloqueos_perfil()
        self.consola.agregar_log("[OK] Perfil de Gemini revisado. Bloqueos removidos.")
        liberar_boton_protegido(self.btn_limpiar_bloqueos)

    def _cargar_plantillas(self) -> None:
        self.combo_plantillas.clear(); self.combo_plantillas.addItem("(Escribir prompt personalizado...)", "")
        if self._servicio_prompts:
            try:
                for p in self._servicio_prompts.listar_plantillas(categoria="ia_web"): self.combo_plantillas.addItem(p.titulo, p.identificador)
            except Exception: pass

    def _al_seleccionar_plantilla(self) -> None:
        c = self.combo_plantillas.currentData()
        if not c: return
        p = self._servicio_prompts.obtener_plantilla(str(c)) if self._servicio_prompts else None
        if p: self.txt_instrucciones.setPlainText(p.contenido); self.consola.agregar_log(f"[INFO] Plantilla cargada: {p.titulo}")

    def _ejecutar_procesamiento(self) -> None:
        if self._hilo_proc and self._hilo_proc.isRunning():
            self.banner.mostrar_advertencia("[ALERTA] Ya hay un procesamiento en curso.")
            liberar_boton_protegido(self.btn_ejecutar, habilitar=True)
            self.btn_cancelar.setEnabled(True)
            return
        op = self.combo_operacion.currentData()
        if op == "extraccion_negocios_imagenes":
            params = self.panel_imagenes_1a1.obtener_parametros()
            if not params or not params.get("campos_activos"):
                QMessageBox.warning(self, "Campos requeridos", "Seleccione carpeta y campos a extraer.")
                liberar_boton_protegido(self.btn_ejecutar, habilitar=True); return
            p_carp = params["carpeta"]

            gestor_cp = GestorCheckpointImagenes(self._enrutador)
            estado_cp = gestor_cp.evaluar_carpeta(p_carp, modulo="gemini")
            archivos_proc = listar_imagenes_carpeta(p_carp)
            modo_esc = "sobrescribir"
            csv_destino = None

            if estado_cp.requiere_decision:
                accion, anexar = solicitar_decision_checkpoint_imagenes(estado_cp, parent=self)
                if accion == "cancelar": liberar_boton_protegido(self.btn_ejecutar, habilitar=True); return
                if accion == "reiniciar_todo":
                    gestor_cp.reiniciar_checkpoint(p_carp, modulo="gemini"); archivos_proc = listar_imagenes_carpeta(p_carp)
                elif accion == "solo_nuevas":
                    archivos_proc = estado_cp.nuevas
                    if anexar and estado_cp.ruta_csv_anterior: modo_esc, csv_destino = "reanudar", estado_cp.ruta_csv_anterior
                else:  # "reprocesar_pendientes_y_fallidas"
                    archivos_proc = estado_cp.fallidas + estado_cp.nuevas
                    if anexar and estado_cp.ruta_csv_anterior: modo_esc, csv_destino = "reanudar", estado_cp.ruta_csv_anterior

            if not archivos_proc:
                QMessageBox.information(self, "Sin pendientes", "Todas las imágenes de esta carpeta ya fueron procesadas con éxito.")
                liberar_boton_protegido(self.btn_ejecutar, habilitar=True); return

            self.btn_ejecutar.setEnabled(False); self.btn_cancelar.setEnabled(True); self.barra_progreso.setValue(0)
            self.consola.agregar_log(f"[INFO] Preparando extracción de imágenes Gemini con {p_carp.name} ({len(archivos_proc)} fotos)...")
            self._hilo_proc = HiloProcesamientoWeb(
                servicio=self._servicio_proc, motor="gemini", tipo_operacion="extraccion_negocios_imagenes", ruta_directa=p_carp,
                campos_activos=params["campos_activos"], instrucciones=params.get("instrucciones_extra", ""),
                rotacion_chat=params.get("rotacion_chat", 2), archivos_especificos=archivos_proc,
                modo_escritura=modo_esc, csv_existente=csv_destino,
                generar_auditoria_md=self.check_auditoria_md.isChecked(), parent=self,
            )
        else:
            ruta_csv = self.panel_archivo.obtener_ruta_csv()
            if not ruta_csv or not ruta_csv.is_file():
                QMessageBox.warning(self, "Archivo requerido", "Seleccione un archivo CSV o Excel válido.")
                liberar_boton_protegido(self.btn_ejecutar, habilitar=True); return
            columnas = self.panel_archivo.obtener_columnas_seleccionadas()
            if not columnas:
                QMessageBox.warning(self, "Columnas requeridas", "Marque al menos una columna para evaluar.")
                liberar_boton_protegido(self.btn_ejecutar, habilitar=True); return
            instr = self.txt_instrucciones.toPlainText().strip()
            if not instr:
                QMessageBox.warning(self, "Prompt requerido", "Ingrese las instrucciones de evaluación.")
                liberar_boton_protegido(self.btn_ejecutar, habilitar=True); return
            hoja = self.panel_archivo.obtener_hoja_seleccionada()
            trabajo = preparar_trabajo_con_dialogo(
                self._enrutador, ruta_csv, "gemini", instr, columnas,
                leer_filas_archivo_tabular(ruta_csv, hoja), {"hoja": hoja}, parent=self,
            )
            if trabajo is None:
                liberar_boton_protegido(self.btn_ejecutar, habilitar=True)
                return
            self.btn_ejecutar.setEnabled(False); self.btn_cancelar.setEnabled(True); self.barra_progreso.setValue(0)
            self.consola.agregar_log(f"[INFO] Preparando corrida Gemini con {ruta_csv.name}...")
            self._hilo_proc = HiloProcesamientoWeb(
                servicio=self._servicio_proc, motor="gemini", ruta_csv=ruta_csv, columnas=columnas,
                instrucciones=instr, tamano_lote=self.spin_lote.value(), rotacion_chat=self.spin_rotacion.value(),
                generar_auditoria_md=self.check_auditoria_md.isChecked(), trabajo_tabular=trabajo, nombre_hoja=hoja, parent=self,
            )
        self._hilo_proc.senial_log.connect(self.consola.agregar_log); self._hilo_proc.progreso_actualizado.connect(self._al_progreso)
        self._hilo_proc.proceso_completado.connect(self._al_completado); self._hilo_proc.proceso_fallido.connect(self._al_fallo)
        self._hilo_proc.start()

    def _al_progreso(self, act: int, tot: int, det: str) -> None:
        pct = int((act / tot) * 100) if tot > 0 else 0; self.barra_progreso.setValue(pct)

    def _al_completado(self, msg: str, ruta_salida: Path) -> None:
        self._ultima_salida = ruta_salida; self.consola.agregar_log(msg)
        if not msg.startswith("[ALERTA]") and "cancelad" not in msg.lower():
            self.barra_progreso.setValue(100)
        if "cancelad" in msg.lower(): self.banner.mostrar_info(f"[INFO] Corrida cancelada. Guardado en: {ruta_salida.name}")
        elif msg.startswith("[ALERTA]"): self.banner.mostrar_advertencia(msg)
        else: self.banner.mostrar_exito(f"[OK] Archivo guardado: {ruta_salida.name}")
        self.btn_ejecutar.setEnabled(True); self.btn_cancelar.setText("Detener Gemini"); self.btn_cancelar.setEnabled(False)
        liberar_boton_protegido(self.btn_ejecutar, habilitar=True)

    def _al_fallo(self, error: str) -> None:
        self.consola.agregar_log(f"[ERROR] {error}"); self.banner.mostrar_error(f"[ERROR] Procesamiento fallido: {error[:100]}")
        self.btn_ejecutar.setEnabled(True); self.btn_cancelar.setText("Detener Gemini"); self.btn_cancelar.setEnabled(False)
        liberar_boton_protegido(self.btn_ejecutar, habilitar=True)

    def _cancelar_procesamiento(self) -> None:
        if self._hilo_proc and self._hilo_proc.isRunning():
            self._hilo_proc.cancelar(); self.consola.agregar_log("[ALERTA] Cancelando corrida Gemini...")
            self.banner.mostrar_en_proceso("[ALERTA] Cancelando corrida Gemini...")
            self.btn_cancelar.setEnabled(False); self.btn_cancelar.setText("Cancelando...")
            liberar_boton_protegido(self.btn_ejecutar, habilitar=True)
            QTimer.singleShot(1500, self._restablecer_botones_cancelacion)

    def _restablecer_botones_cancelacion(self) -> None:
        self.btn_cancelar.setText("Detener Gemini"); self.btn_cancelar.setEnabled(False)
        liberar_boton_protegido(self.btn_ejecutar, habilitar=True)

    def _abrir_carpeta_salida(self) -> None:
        carpeta = self._ultima_salida.parent if self._ultima_salida and self._ultima_salida.exists() else self._enrutador.extracciones / "gemini"
        carpeta.mkdir(parents=True, exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(carpeta.resolve())))
        liberar_boton_protegido(self.btn_abrir_salida)

    def _limpiar_formulario(self) -> None:
        self.panel_archivo.limpiar(); self.panel_imagenes_1a1.limpiar(); self.txt_instrucciones.clear()
        self.combo_plantillas.setCurrentIndex(0); self.spin_lote.setValue(5); self.spin_rotacion.setValue(2)
        self.barra_progreso.setValue(0); self.banner.mostrar_info("[INFO] Formulario Gemini restablecido.")

    def _al_volver(self) -> None:
        self._cancelar_procesamiento(); liberar_boton_protegido(self.btn_ejecutar, habilitar=True); self.volver_solicitado.emit()

    def adaptar_modo(self, modo: ModoPantalla) -> None:
        pass
