"""Vista operativa para ejecucion masiva y configuracion de DeepSeek y Gemini Web."""

from __future__ import annotations

import os
from pathlib import Path
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QGroupBox, QHBoxLayout, QMessageBox,
    QRadioButton, QTabWidget, QVBoxLayout, QWidget,
)

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.comun.gestor_lote_imagenes import (
    listar_imagenes_carpeta,
    verificar_estado_carpeta_imagenes,
)
from procesos_ia.aplicacion.ia_web.motores.servicio_procesamiento_web import ServicioProcesamientoWeb
from procesos_ia.infraestructura.web.base.configuracion_web import (
    ConfiguracionWeb,
    PERFIL_MOTORES_WEB,
)
from procesos_ia.interfaz.componentes.banner_notificacion import BannerNotificacion
from procesos_ia.interfaz.componentes.barra_navegacion import BarraNavegacionSubvista
from procesos_ia.interfaz.ia_web.componentes.consola_ia_general import ConsolaIAGeneral
from procesos_ia.interfaz.ia_web.componentes.panel_opciones_web import PanelOpcionesAvanzadasWeb
from procesos_ia.interfaz.ia_web.hilos.hilo_navegador import HiloLanzarNavegador
from procesos_ia.interfaz.ia_web.hilos.hilo_procesamiento_web import HiloProcesamientoWeb
from procesos_ia.interfaz.protector_botones import liberar_boton_protegido
from procesos_ia.interfaz.responsivo import ModoPantalla


class VistaConfiguracionMotores(QWidget):
    """Panel operativo interactivo para enviar datos e imagenes a Gemini y DeepSeek."""

    volver_solicitado = Signal(); motor_configurado = Signal(str, object)
    ia_general_solicitado = Signal(); plantillas_web_solicitadas = Signal()

    def __init__(
        self, motor_actual: str = "gemini", configuracion_web: ConfiguracionWeb | None = None, parent: QWidget | None = None,
        enrutador: EnrutadorSalidas | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("IA Web: Procesamiento y Motores (DeepSeek y Gemini)")
        self._motor_actual = motor_actual if motor_actual in ("gemini", "deepseek") else "gemini"
        self._config_web = configuracion_web or ConfiguracionWeb(nombre_perfil=PERFIL_MOTORES_WEB)
        self._servicio_proc = ServicioProcesamientoWeb(configuracion_web=self._config_web, enrutador=enrutador)
        self._hilo_nav: HiloLanzarNavegador | None = None
        self._hilo_proc: HiloProcesamientoWeb | None = None
        self._ultima_salida: Path | None = None
        self._iniciar_ui(); self._sincronizar_desde_configuracion(); self._cargar_plantillas_ia_web()

    def _iniciar_ui(self) -> None:
        from procesos_ia.interfaz.componentes.contenedor_responsivo import ContenedorPantallaResponsiva

        layout_raiz = QVBoxLayout(self); layout_raiz.setContentsMargins(0, 0, 0, 0)
        self.contenedor = ContenedorPantallaResponsiva(self); layout_raiz.addWidget(self.contenedor)
        self.barra_nav = BarraNavegacionSubvista("Módulo IA Web (DeepSeek / Gemini)", "Restablecer", self)
        self.barra_nav.volver_solicitado.connect(self._al_volver); self.barra_nav.limpiar_solicitado.connect(self._restablecer_por_defecto)
        self.contenedor.agregar_widget(self.barra_nav); self.banner = BannerNotificacion(self); self.contenedor.agregar_widget(self.banner)

        # 1. Selector de Motor Web
        grupo_motores = QGroupBox("Motor Web Destino", self); layout_m = QHBoxLayout(grupo_motores); layout_m.setContentsMargins(8, 4, 8, 4)
        self.radio_gemini, self.radio_deepseek = QRadioButton("Google Gemini Web (gemini.google.com)", self), QRadioButton("DeepSeek Web (chat.deepseek.com)", self)
        self.grupo_botones = QButtonGroup(self); self.grupo_botones.addButton(self.radio_gemini, 1); self.grupo_botones.addButton(self.radio_deepseek, 0)
        self.grupo_botones.idToggled.connect(self._al_cambiar_seleccion_motor)
        layout_m.addWidget(self.radio_gemini); layout_m.addWidget(self.radio_deepseek); self.contenedor.agregar_widget(grupo_motores)

        # 2. Consola de bitacora abajo (creada primero para que los componentes puedan conectar logs)
        self.consola = ConsolaIAGeneral(self); self.consola.setMinimumHeight(190)

        # 3. Pestañas de Operacion y Configuracion
        self.tabs = QTabWidget(self); self.tab_operacion = QWidget(self); self._iniciar_tab_operacion()
        self.tab_config = PanelOpcionesAvanzadasWeb(self); self.panel_opciones, self.grupo_web = self.tab_config, self.tab_config
        self.combo_modo, self.btn_abrir_navegador = self.tab_config.combo_modo, self.tab_config.btn_abrir_navegador
        self.btn_limpiar_bloqueos, self.btn_aplicar = self.tab_config.btn_limpiar_bloqueos, self.tab_config.btn_aplicar
        self.tab_config.abrir_navegador_solicitado.connect(self._abrir_navegador_manual)
        self.tab_config.limpiar_bloqueos_solicitado.connect(self._limpiar_bloqueos_perfil); self.tab_config.aplicar_solicitado.connect(self._aplicar_y_volver)
        self.tabs.addTab(self.tab_operacion, "Procesamiento de Archivos (Texto / Imágenes)")
        self.tabs.addTab(self.tab_config, "Configuración Avanzada del Navegador"); self.contenedor.agregar_widget(self.tabs)
        self.contenedor.agregar_widget(self.consola)

    def _iniciar_tab_operacion(self) -> None:
        from procesos_ia.interfaz.ia_web.componentes.operacion_motores import construir_operacion_motores
        construir_operacion_motores(self)

    def _al_cambiar_operacion(self) -> None:
        op = self.combo_operacion.currentData()
        es_neg = op == "extraccion_negocios_imagenes"
        self.panel_imagenes_1a1.setVisible(es_neg)
        self.grupo_prompt.setVisible(not es_neg); self.widget_opts.setVisible(not es_neg)
        if es_neg:
            self.panel_archivo.setVisible(False); self.grupo_directo.setVisible(False); return
        es_csv_texto, es_csv_img = op == "csv_texto", op == "csv_imagen"
        es_csv = es_csv_texto or es_csv_img
        self.panel_archivo.setVisible(es_csv); self.panel_archivo.configurar_modo_imagen(es_csv_img)
        self.grupo_directo.setVisible(not es_csv)
        if op == "carpeta_imagenes":
            self.grupo_directo.setTitle("Entrada de Carpeta de Imágenes (Modo Tsukuyomi)")
            self.lbl_directo.setText("Carpeta de Imágenes:"); self.btn_examinar_directo.setText("Examinar Carpeta...")
        elif op == "imagen_individual":
            self.grupo_directo.setTitle("Entrada de Imagen Individual")
            self.lbl_directo.setText("Archivo de Imagen:"); self.btn_examinar_directo.setText("Examinar Imagen...")
        self.spin_lote.setEnabled(es_csv_texto)
        self.input_imagenes.setVisible(es_csv_img); self.btn_examinar_imagenes.setVisible(es_csv_img)

    def _abrir_dialogo_directo(self) -> None:
        op, base_dir = self.combo_operacion.currentData(), self._servicio_proc._enrutador.imagenes
        base_dir.mkdir(parents=True, exist_ok=True)
        if op == "carpeta_imagenes":
            d = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta", str(base_dir))
            if d: self.input_directo.setText(d)
        else:
            f, _ = QFileDialog.getOpenFileName(self, "Seleccionar Imagen", str(base_dir), "Imágenes (*.jpg *.jpeg *.png *.webp *.bmp)")
            if f: self.input_directo.setText(f)

    def _obtener_servicio_prompts(self):
        if not hasattr(self, "_servicio_prompts") or self._servicio_prompts is None:
            from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
            from procesos_ia.infraestructura.prompts.repositorio_md import RepositorioPromptsMd
            self._servicio_prompts = ServicioCatalogoPrompts(RepositorioPromptsMd(self._servicio_proc._enrutador.plantillas))
        return self._servicio_prompts

    def _cargar_plantillas_ia_web(self) -> None:
        c_actual = self.combo_plantillas.currentData()
        from procesos_ia.aplicacion.ia_web.comun.prompts_ia_web import poblar_combo_plantillas_ia_web
        poblar_combo_plantillas_ia_web(self.combo_plantillas, self._obtener_servicio_prompts())
        if c_actual:
            idx = self.combo_plantillas.findData(c_actual)
            if idx >= 0: self.combo_plantillas.setCurrentIndex(idx); self._al_seleccionar_plantilla()

    def _al_seleccionar_plantilla(self) -> None:
        c = self.combo_plantillas.currentData()
        if not c: return
        p = self._obtener_servicio_prompts().obtener_plantilla(str(c))
        if p is not None:
            self.txt_instrucciones.setPlainText(p.contenido); self.consola.agregar_log(f"[INFO] Plantilla cargada: {p.titulo}")
        else:
            self.txt_instrucciones.setPlainText(str(c)); self.consola.agregar_log(f"[INFO] Plantilla cargada: {self.combo_plantillas.currentText()}")

    def _ejecutar_procesamiento_web(self) -> None:
        if self._hilo_proc is not None and self._hilo_proc.isRunning():
            self.banner.mostrar_advertencia("[ALERTA] Ya hay un proceso en ejecución en el navegador. Espere o deténgalo."); return
        op = self.combo_operacion.currentData()
        motor = "gemini" if self.radio_gemini.isChecked() else "deepseek"
        self._servicio_proc._config = self._construir_configuracion_web()
        rot = self.spin_rotacion.value()
        if op == "extraccion_negocios_imagenes":
            params_img = self.panel_imagenes_1a1.obtener_parametros()
            if not params_img:
                self.banner.mostrar_error("[ALERTA] Seleccione una carpeta válida con imágenes."); return
            if not params_img.get("campos_activos"):
                self.banner.mostrar_error("[ALERTA] Seleccione al menos un campo a extraer."); return
            p_carp = params_img["carpeta"]
            manif = getattr(self._servicio_proc._enrutador, "manifiesto_imagenes", None)
            n_manif = manif.obtener_procesadas(p_carp.name) if manif else None
            dest = params_img.get("carpeta_salida")
            rama = self._servicio_proc._enrutador.gestor_procesos(dest).rama(motor)
            estado = verificar_estado_carpeta_imagenes(p_carp, rama, prefijo=f"{motor}_imagenes", columna_fuente="archivo_imagen", nombres_manifiesto=n_manif)
            if estado.total_imagenes == 0:
                self.banner.mostrar_error("[ALERTA] La carpeta no contiene imágenes compatibles."); return
            if not estado.hay_nuevas:
                box = QMessageBox(self); box.setWindowTitle("Carpeta al día")
                d_csv = f"\nCSV: {estado.csv_existente.resolve()}" if estado.csv_existente else "\nHistorial: Manifiesto integrado"
                box.setText(f"No hay imágenes nuevas en {motor.upper()}.\n\nCarpeta: {p_carp.resolve()}{d_csv}")
                rep = box.addButton("Reprocesar todo desde cero", QMessageBox.ButtonRole.DestructiveRole)
                box.addButton("Aceptar", QMessageBox.ButtonRole.AcceptRole); box.exec()
                if box.clickedButton() != rep: return
                if manif: manif.limpiar_carpeta(p_carp.name)
                estado.imagenes_pendientes, estado.csv_existente = listar_imagenes_carpeta(p_carp), None
            self._hilo_proc = HiloProcesamientoWeb(
                self._servicio_proc, motor, tipo_operacion=op, ruta_directa=p_carp,
                campos_activos=params_img["campos_activos"], instrucciones=params_img.get("instrucciones_extra", ""),
                rotacion_chat=params_img.get("rotacion_chat", 2), archivos_especificos=estado.imagenes_pendientes,
                modo_escritura=("reanudar" if estado.csv_existente else "sobrescribir"),
                csv_existente=estado.csv_existente, carpeta_salida=dest, parent=self,
            )
        else:
            inst = self.txt_instrucciones.toPlainText().strip()
            if not inst:
                self.banner.mostrar_error("[ALERTA] Ingrese instrucciones o seleccione una plantilla."); return
            if op in ("csv_texto", "csv_imagen"):
                ruta = self.panel_archivo.obtener_ruta_csv()
                if not ruta or not ruta.is_file():
                    self.banner.mostrar_error("[ALERTA] Seleccione un archivo CSV o Excel válido."); return
                cols = self.panel_archivo.obtener_columnas_seleccionadas()
                col_img = self.panel_archivo.obtener_columna_imagen() if op == "csv_imagen" else None
                if not cols and not col_img:
                    self.banner.mostrar_error("[ALERTA] Seleccione al menos una columna a procesar."); return
                if op == "csv_imagen" and not col_img:
                    self.banner.mostrar_error("[ALERTA] Seleccione la columna que contiene los nombres de imagen."); return
                carp_txt = self.input_imagenes.text().strip()
                carp = Path(carp_txt) if carp_txt else None
                if op == "csv_imagen" and (not carp or not carp.is_dir()):
                    self.banner.mostrar_error("[ALERTA] Seleccione una carpeta válida de imágenes."); return
                self._hilo_proc = HiloProcesamientoWeb(
                    self._servicio_proc, motor, ruta_csv=ruta, columnas=cols, instrucciones=inst,
                    tamano_lote=self.spin_lote.value(), columna_imagen=col_img, carpeta_imagenes=carp,
                    rotacion_chat=rot, parent=self,
                )
            else:
                txt_d = self.input_directo.text().strip()
                if not txt_d:
                    self.banner.mostrar_error("[ALERTA] Seleccione la carpeta o archivo de imagen."); return
                p_d = Path(txt_d)
                if (op == "carpeta_imagenes" and not p_d.is_dir()) or (op == "imagen_individual" and not p_d.is_file()):
                    self.banner.mostrar_error("[ALERTA] La ruta seleccionada no existe en disco."); return
                self._hilo_proc = HiloProcesamientoWeb(
                    self._servicio_proc, motor, instrucciones=inst, rotacion_chat=rot,
                    tipo_operacion=op, ruta_directa=p_d, parent=self,
                )
        self.btn_ejecutar.setEnabled(False); self.radio_gemini.setEnabled(False); self.radio_deepseek.setEnabled(False)
        self.combo_operacion.setEnabled(False); self.btn_cancelar.setText("Detener"); liberar_boton_protegido(self.btn_cancelar, habilitar=True)
        self.barra_progreso.setValue(0); self.banner.mostrar_en_proceso(f"[INFO] Procesando en {motor.upper()}...")
        for sig, fn in ((self._hilo_proc.senial_log, self.consola.agregar_log), (self._hilo_proc.progreso_actualizado, self._al_progresar),
                        (self._hilo_proc.proceso_completado, self._al_completar), (self._hilo_proc.proceso_fallido, self._al_fallar)):
            sig.connect(fn)
        self._hilo_proc.start()

    def _al_progresar(self, act: int, tot: int, det: str) -> None:
        pct = int((act / tot) * 100) if tot > 0 else 0
        self.barra_progreso.setValue(pct); self.banner.mostrar_en_proceso(f"[INFO] {det} ({pct}%)")

    def _al_completar(self, msg: str, salida: Path) -> None:
        self._ultima_salida = salida; self.barra_progreso.setValue(100); self._restablecer_estado_controles()
        self.banner.mostrar_exito(msg); self.consola.agregar_log(f"[OK] Archivo guardado: {salida}")

    def _al_fallar(self, error: str) -> None:
        self._restablecer_estado_controles(); self.banner.mostrar_error(f"[ERROR] {error}"); self.consola.agregar_log(f"[ERROR] {error}")

    def _restablecer_estado_controles(self) -> None:
        self.btn_ejecutar.setEnabled(True); self.radio_gemini.setEnabled(True); self.radio_deepseek.setEnabled(True)
        self.combo_operacion.setEnabled(True); self.btn_cancelar.setText("Detener")
        liberar_boton_protegido(self.btn_cancelar, habilitar=False)

    def _cancelar_procesamiento(self) -> None:
        self.btn_cancelar.setEnabled(False); self.btn_cancelar.setText("Cancelando...")
        if self._hilo_proc and self._hilo_proc.isRunning(): self._hilo_proc.cancelar(); self.consola.agregar_log("[ALERTA] Detención solicitada...")

    def _abrir_carpeta_salida(self) -> None:
        motor = "gemini" if self.radio_gemini.isChecked() else "deepseek"
        c = self._ultima_salida.parent if self._ultima_salida else self._servicio_proc._enrutador.gestor_procesos().rama(motor)
        c.mkdir(parents=True, exist_ok=True); os.startfile(str(c)) if hasattr(os, "startfile") else None

    def _abrir_dialogo_imagenes(self) -> None:
        d = self._servicio_proc._enrutador.imagenes; d.mkdir(parents=True, exist_ok=True)
        sel = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta", str(self._config_web.carpeta_imagenes or d))
        if sel: self.input_imagenes.setText(sel)

    spin_espera = property(lambda self: self.panel_opciones.spin_espera)

    def _sincronizar_desde_configuracion(self) -> None:
        self.radio_gemini.setChecked(self._motor_actual == "gemini"); self.radio_deepseek.setChecked(self._motor_actual != "gemini")
        self.combo_modo.setCurrentIndex(1 if self._config_web.modo_procesamiento == "individual" else 0)
        self.input_imagenes.setText(str(self._config_web.carpeta_imagenes or ""))
        self.spin_rotacion.setValue(self._config_web.max_consultas_por_chat); self.panel_opciones.sincronizar_desde_config(self._config_web)

    def _al_cambiar_seleccion_motor(self, _id: int, marcado: bool) -> None:
        if marcado:
            m = "Gemini" if self.radio_gemini.isChecked() else "DeepSeek"
            self.banner.mostrar_info(f"[INFO] Motor activo: {m} Web. Listo para procesar.")

    def _construir_configuracion_web(self) -> ConfiguracionWeb:
        v, r = self.panel_opciones.obtener_ventana_web(), self.input_imagenes.text().strip()
        return ConfiguracionWeb(
            ventana=v, tiempo_espera_respuesta_segundos=self.panel_opciones.tiempo_espera(),
            max_consultas_por_chat=self.spin_rotacion.value(), carpeta_imagenes=Path(r) if r else None,
            modo_procesamiento="individual" if self.combo_modo.currentIndex() == 1 else "lote",
            nombre_perfil=PERFIL_MOTORES_WEB,
        )

    def _abrir_navegador_manual(self) -> None:
        url = self._config_web.url_deepseek if self.radio_deepseek.isChecked() else self._config_web.url_gemini
        self.banner.mostrar_en_proceso(f"[INFO] Abriendo navegador en {url}...")
        if self._hilo_nav is not None and self._hilo_nav.isRunning(): return
        self._hilo_nav = HiloLanzarNavegador(url, self._construir_configuracion_web(), self)
        self._hilo_nav.senial_exito.connect(lambda msg: self.banner.mostrar_exito(f"[OK] {msg}"))
        self._hilo_nav.senial_error.connect(lambda err: self.banner.mostrar_error(f"[ERROR] {err}"))
        self._hilo_nav.start()

    def _limpiar_bloqueos_perfil(self) -> None:
        self.banner.mostrar_exito("[OK] Bloqueos eliminados.") if self._config_web.limpiar_bloqueos_perfil() else self.banner.mostrar_info("[INFO] Sin bloqueos.")

    def _restablecer_por_defecto(self) -> None:
        self._config_web = ConfiguracionWeb(); self._sincronizar_desde_configuracion()
        self.banner.mostrar_info("[INFO] Valores restablecidos a los parámetros predeterminados.")

    def _aplicar_y_volver(self) -> None:
        m = "gemini" if self.radio_gemini.isChecked() else "deepseek"
        self.motor_configurado.emit(m, self._construir_configuracion_web()); self.volver_solicitado.emit()

    def _al_volver(self) -> None: self.volver_solicitado.emit()

    def adaptar_modo(self, modo: ModoPantalla) -> None:
        c = modo == ModoPantalla.COMPACTO
        self.btn_ejecutar.setText("Iniciar Web" if c else "Iniciar Procesamiento Web")
        self.btn_ia_general.setText("IA General (Lens)" if c else "IA General (Google Lens / Modo IA)")
