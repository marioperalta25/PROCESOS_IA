"""Vista interactiva para el modulo de IA General (Google Lens y Modo IA)."""

from __future__ import annotations

import os; from dataclasses import replace
from pathlib import Path
from PySide6.QtCore import Signal, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from procesos_ia.aplicacion.comun.gestor_checkpoint_imagenes import GestorCheckpointImagenes
from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.comun.gestor_lote_imagenes import listar_imagenes_carpeta
from procesos_ia.interfaz.comun.dialogo_checkpoint_imagenes import solicitar_decision_checkpoint_imagenes
from procesos_ia.interfaz.comun.preparacion_tabular import preparar_trabajo_con_dialogo
from procesos_ia.aplicacion.ia_web.visual_1a1.servicio_ia_general import ServicioIAGeneral
from procesos_ia.dominio.ia_web.desglosador_telefonos import desglosar_ficha_por_telefono
from procesos_ia.dominio.ia_web.ficha_negocio import FichaNegocioLens
from procesos_ia.infraestructura.web.base.configuracion_web import ConfiguracionWeb, PERFIL_IA_GENERAL
from procesos_ia.infraestructura.web.base.gestor_sesion_nodriver import GestorSesionNodriver
from procesos_ia.interfaz.componentes.banner_notificacion import BannerNotificacion
from procesos_ia.interfaz.componentes.barra_navegacion import BarraNavegacionSubvista
from procesos_ia.interfaz.componentes.contenedor_responsivo import ContenedorPantallaResponsiva
from procesos_ia.interfaz.ia_web.componentes.barra_acciones_ia_general import BarraAccionesIAGeneral
from procesos_ia.interfaz.ia_web.componentes.consola_ia_general import ConsolaIAGeneral
from procesos_ia.interfaz.ia_web.componentes.panel_archivo_general import PanelArchivoGeneral
from procesos_ia.interfaz.ia_web.conversacional.panel_modo_chat import PanelModoChat
from procesos_ia.interfaz.ia_web.conversacional.panel_modo_chat_imagenes import PanelModoChatImagenes
from procesos_ia.interfaz.ia_web.conversacional.panel_modo_ia_urls import PanelModoIAUrls
from procesos_ia.interfaz.ia_web.hilos.hilo_ia_general import HiloIAGeneral
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido, liberar_boton_protegido
from procesos_ia.interfaz.responsivo import ModoPantalla, configurar_tabla_responsiva


class VistaIAGeneral(QWidget):
    """Panel de operacion para extracciones visuales en Google Lens y Modo IA."""

    volver_solicitado = Signal()

    def __init__(
        self, gestor_sesion: GestorSesionNodriver | None = None,
        configuracion_web: ConfiguracionWeb | None = None,
        servicio_prompts: object | None = None, parent: QWidget | None = None,
        enrutador: EnrutadorSalidas | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("IA General: Google Lens y Modo IA")
        self._config_web = replace(configuracion_web or ConfiguracionWeb(), nombre_perfil=PERFIL_IA_GENERAL)
        self._gestor = gestor_sesion or GestorSesionNodriver(self._config_web)
        self._servicio = ServicioIAGeneral(self._gestor, self._config_web, enrutador=enrutador)
        self._servicio_prompts = servicio_prompts or self._crear_servicio_prompts()
        self._hilo, self._carpeta_salida_custom, self._cancelando = None, None, False
        self._iniciar_ui(); self._actualizar_visibilidad()

    def _crear_servicio_prompts(self) -> object:
        from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
        from procesos_ia.infraestructura.prompts.repositorio_md import RepositorioPromptsMd; return ServicioCatalogoPrompts(RepositorioPromptsMd(self._servicio.enrutador.plantillas))

    def _iniciar_ui(self) -> None:
        layout_raiz = QVBoxLayout(self); layout_raiz.setContentsMargins(0, 0, 0, 0)
        self.contenedor = ContenedorPantallaResponsiva(self); layout_raiz.addWidget(self.contenedor)
        self.barra_nav = BarraNavegacionSubvista("Módulo IA General (Google Lens / Modo IA)", "Limpiar", self)
        self.barra_nav.volver_solicitado.connect(self._al_volver); self.barra_nav.limpiar_solicitado.connect(self._limpiar_formulario)
        self.contenedor.agregar_widget(self.barra_nav)
        self.banner = BannerNotificacion(self); self.contenedor.agregar_widget(self.banner)

        layout_modo = QHBoxLayout(); layout_modo.addWidget(QLabel("Operación:", self))
        self.combo_flujo = QComboBox(self)
        flujos = (("Modo IA de Google (Prompt y Lotes CSV con |)", "modo_ia"),
                  ("Modo IA con Imágenes (1 a 1 en Chat)", "modo_ia_imagenes"),
                  ("Modo IA con CSV de URLs (Lotes en Chat)", "modo_ia_urls"),
                  ("Google Lens con CSV de Imágenes / URLs", "csv_lens"),
                  ("Google Lens con Carpeta de Imágenes (1 a 1)", "carpeta"),
                  ("Google Lens con URL de Imagen Individual", "url"))
        for t, d in flujos: self.combo_flujo.addItem(t, d)
        self.combo_flujo.currentIndexChanged.connect(self._actualizar_visibilidad)
        layout_modo.addWidget(self.combo_flujo, stretch=1)
        self.check_auditoria_md = QCheckBox("Generar auditoría (.md)", self)
        self.check_auditoria_md.setChecked(getattr(self._config_web, "generar_auditoria_md", True))
        layout_modo.addWidget(self.check_auditoria_md)
        self.contenedor.agregar_layout(layout_modo)

        self.lbl_guia_flujo = QLabel(self); self.lbl_guia_flujo.setWordWrap(True)
        self.lbl_guia_flujo.setStyleSheet("color: #58615B; font-size: 11px;")
        self.contenedor.agregar_widget(self.lbl_guia_flujo)

        self.panel_modo_chat = PanelModoChat(self._servicio_prompts, self._servicio.enrutador, self)
        self.panel_chat_imagenes = PanelModoChatImagenes(self._servicio.enrutador, self, nombre_modulo="Modo IA Imágenes")
        self.panel_archivo = PanelArchivoGeneral(self, enrutador=self._servicio.enrutador, nombre_modulo="Google Lens")
        self.panel_modo_ia_urls = PanelModoIAUrls(self)
        for p in (self.panel_modo_chat, self.panel_chat_imagenes, self.panel_archivo):
            p.log_notificado.connect(self._registrar_log); self.contenedor.agregar_widget(p)
        self.contenedor.agregar_widget(self.panel_modo_ia_urls)

        self.grupo_alt = QGroupBox("Entrada Específica (URL / Carpeta)", self)
        layout_alt = QHBoxLayout(self.grupo_alt)
        self.input_alt, self.btn_examinar_alt = QLineEdit(self), QPushButton("Examinar...", self)
        conectar_boton_protegido(self.btn_examinar_alt, self._abrir_dialogo_alt, "[INFO]...", 500)
        layout_alt.addWidget(self.input_alt, stretch=1); layout_alt.addWidget(self.btn_examinar_alt)
        self.grupo_alt.setVisible(False); self.contenedor.agregar_widget(self.grupo_alt)

        self.barra_progreso = QProgressBar(self); self.barra_progreso.setRange(0, 100); self.barra_progreso.setValue(0)
        self.contenedor.agregar_widget(self.barra_progreso)
        self.barra_acciones = BarraAccionesIAGeneral(self._ejecutar_accion, self._cancelar_proceso, self._cambiar_carpeta_salida, self._abrir_carpeta_salida, self)
        ba = self.barra_acciones; self.btn_ejecutar, self.btn_cancelar, self.btn_destino, self.btn_abrir_salida = ba.btn_ejecutar, ba.btn_cancelar, ba.btn_destino, ba.btn_abrir_salida
        self.contenedor.agregar_widget(self.barra_acciones)

        self.consola = ConsolaIAGeneral(self); self.consola.setMinimumHeight(190); self.contenedor.agregar_widget(self.consola)
        self.tabla = QTableWidget(0, 7, self); self.tabla.setMinimumHeight(150); self.tabla.setHorizontalHeaderLabels(["ID", "Estado IA", "Propietario", "Negocio", "Categoría", "Teléfono", "Ubicación"])
        configurar_tabla_responsiva(self.tabla); self.contenedor.agregar_widget(self.tabla)

    def _actualizar_visibilidad(self) -> None:
        modo = self.combo_flujo.currentData()
        self.panel_modo_chat.setVisible(modo == "modo_ia"); self.panel_chat_imagenes.setVisible(modo == "modo_ia_imagenes")
        self.panel_archivo.setVisible(modo in ("csv_lens", "modo_ia_urls")); self.panel_modo_ia_urls.setVisible(modo == "modo_ia_urls")
        self.grupo_alt.setVisible(modo in ("carpeta", "url"))
        if modo in ("csv_lens", "modo_ia_urls"): self.panel_archivo.configurar_modo_imagen(True)
        self.btn_examinar_alt.setVisible(modo == "carpeta")

    def _abrir_dialogo_alt(self) -> None:
        from procesos_ia.interfaz.comun.gestor_rutas_recientes import GestorRutasRecientes
        gr = GestorRutasRecientes(); dir_img = gr.obtener_ruta_imagenes(self.input_alt.text() or self._servicio.enrutador.imagenes)
        ruta = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta", dir_img)
        if ruta: gr.guardar_ruta_imagenes(ruta); self.input_alt.setText(ruta); self._registrar_log(f"[INFO] Carpeta: {ruta}")

    def _verificar_carpeta_con_dialogo(self, p_carp: Path, modulo: str) -> tuple[list[Path], str, Path | None] | None:
        gestor_cp = GestorCheckpointImagenes(self._servicio.enrutador)
        estado_cp = gestor_cp.evaluar_carpeta(p_carp, modulo=modulo)
        if estado_cp.total_disco == 0:
            self.banner.mostrar_error("[ERROR] La carpeta seleccionada no contiene imágenes compatibles."); return None
        archivos_proc, modo_esc, csv_destino = listar_imagenes_carpeta(p_carp), "sobrescribir", None
        if estado_cp.requiere_decision:
            accion, anexar = solicitar_decision_checkpoint_imagenes(estado_cp, parent=self)
            if accion == "cancelar": return None
            if accion == "reiniciar_todo":
                gestor_cp.reiniciar_checkpoint(p_carp, modulo=modulo); archivos_proc = listar_imagenes_carpeta(p_carp)
            elif accion == "solo_nuevas":
                archivos_proc = estado_cp.nuevas
                if anexar and estado_cp.ruta_csv_anterior: modo_esc, csv_destino = "reanudar", estado_cp.ruta_csv_anterior
            else:
                archivos_proc = estado_cp.fallidas + estado_cp.nuevas
                if anexar and estado_cp.ruta_csv_anterior: modo_esc, csv_destino = "reanudar", estado_cp.ruta_csv_anterior
        if not archivos_proc:
            QMessageBox.information(self, "Sin pendientes", "Todas las imágenes de esta carpeta ya fueron procesadas con éxito."); return None
        return archivos_proc, modo_esc, csv_destino

    def _resolver_modo_ia(self) -> tuple[str, dict] | None:
        from procesos_ia.interfaz.ia_web.conversacional.preparacion_modo_ia import resolver_modo_ia
        return resolver_modo_ia(self.panel_modo_chat, self._servicio.enrutador, self._carpeta_salida_custom, self.banner, self)

    def _ejecutar_accion(self) -> None:
        try:
            self._iniciar_accion()
        except Exception as error:
            self._al_error(str(error))

    def _iniciar_accion(self) -> None:
        if self._hilo is not None and self._hilo.isRunning():
            self.banner.mostrar_advertencia("[ALERTA] Ya hay un proceso en ejecución."); return
        def abortar(msg: str) -> None:
            self.banner.mostrar_error(msg); self._registrar_log(msg); liberar_boton_protegido(self.btn_ejecutar, habilitar=True)
        modo, params, tipo = self.combo_flujo.currentData(), {}, ""
        if modo == "modo_ia":
            res_ia = self._resolver_modo_ia()
            if not res_ia: liberar_boton_protegido(self.btn_ejecutar, habilitar=True); return
            tipo, params = res_ia
        elif modo == "modo_ia_imagenes":
            p_img = self.panel_chat_imagenes.obtener_parametros()
            if not p_img: return abortar("[ERROR] Seleccione una carpeta válida con imágenes.")
            if not p_img.get("campos_activos"): return abortar("[ERROR] Seleccione al menos un campo a extraer.")
            res = self._verificar_carpeta_con_dialogo(p_img["carpeta"], "modo_ia")
            if not res: liberar_boton_protegido(self.btn_ejecutar, habilitar=True); return
            archs, modo_esc, csv_prev = res
            p_img.update({"archivos": archs, "modo_escritura": modo_esc, "csv_existente": csv_prev}); tipo, params = "modo_ia_imagenes", p_img
        elif modo in ("csv_lens", "modo_ia_urls"):
            ruta_csv, col = self.panel_archivo.obtener_ruta_csv(), self.panel_archivo.obtener_columna_imagen()
            if not ruta_csv or not ruta_csv.is_file(): return abortar("[ERROR] Seleccione un CSV válido.")
            if not col: return abortar("[ERROR] Seleccione la columna que contiene las imágenes.")
            hoja = self.panel_archivo.obtener_hoja_seleccionada()
            from procesos_ia.aplicacion.ia_web.visual_1a1.procesador_archivo_urls import leer_filas_archivo_tabular
            filas = leer_filas_archivo_tabular(ruta_csv, nombre_hoja=hoja)
            if modo == "modo_ia_urls":
                p_urls = self.panel_modo_ia_urls.obtener_parametros()
                if not p_urls["campos_activos"]: return abortar("[ERROR] Seleccione al menos un campo a extraer.")
                from procesos_ia.aplicacion.ia_web.conversacional.procesador_urls_modo_ia import construir_instrucciones_urls_modo_ia
                inst_u = construir_instrucciones_urls_modo_ia(p_urls["campos_activos"], p_urls["instrucciones_extra"])
                trabajo = preparar_trabajo_con_dialogo(self._servicio.enrutador, ruta_csv, "modo_ia", inst_u, [col], filas, {"hoja": hoja, "columna_url": col}, self._carpeta_salida_custom, self)
                if trabajo is None: self._registrar_log("[INFO] Preparación cancelada o sin filas pendientes."); liberar_boton_protegido(self.btn_ejecutar, habilitar=True); return
                params = {**p_urls, "filas": trabajo.filas_pendientes, "columna": col, "nombre_salida": f"urls_{ruta_csv.stem}", "trabajo_tabular": trabajo}; tipo = "modo_ia_urls"
            else:
                params = {"ruta_csv": ruta_csv, "columna": col, "nombre_hoja": hoja}
                trabajo = preparar_trabajo_con_dialogo(self._servicio.enrutador, ruta_csv, "imagenes", "", [col], filas, {"hoja": hoja, "columna_imagen": col}, self._carpeta_salida_custom, self)
                if trabajo is None: self._registrar_log("[INFO] Preparación de CSV/Excel cancelada o sin filas pendientes."); liberar_boton_protegido(self.btn_ejecutar, habilitar=True); return
                self._registrar_log(f"[INFO] Trabajo CSV/Excel preparado: {ruta_csv.name} | columna '{col}' | {len(trabajo.filas_pendientes)} pendientes.")
                params["trabajo_tabular"] = trabajo; tipo = "csv_imagenes"
        elif modo == "carpeta":
            c = self.input_alt.text().strip().strip("\"'")
            if not c or not Path(c).is_dir(): return abortar("[ERROR] Seleccione una carpeta válida de imágenes.")
            res = self._verificar_carpeta_con_dialogo(Path(c), "imagenes")
            if not res: liberar_boton_protegido(self.btn_ejecutar, habilitar=True); return
            tipo, params = "carpeta_imagenes", {"carpeta": Path(c), "archivos": res[0], "modo_escritura": res[1], "csv_existente": res[2]}
        elif modo == "url":
            u = self.input_alt.text().strip()
            if not u or not (u.startswith("http://") or u.startswith("https://")): return abortar("[ERROR] Ingrese una URL válida (http/https).")
            tipo, params = "imagen_individual", {"fuente": u, "id_registro": "url_individual"}

        if self._carpeta_salida_custom and "carpeta_salida" not in params: params["carpeta_salida"] = self._carpeta_salida_custom
        params["generar_auditoria_md"] = self.check_auditoria_md.isChecked()
        self._cancelando = False; self.btn_ejecutar.setEnabled(False); self.combo_flujo.setEnabled(False)
        self.btn_cancelar.setText("Detener"); liberar_boton_protegido(self.btn_cancelar, habilitar=True); self.barra_progreso.setValue(0)
        self.banner.mostrar_en_proceso("[INFO] Ejecutando tarea en navegador compartido...")
        self._registrar_log(f"[INFO] Iniciando tarea en segundo plano ({tipo})...")
        self._hilo = HiloIAGeneral(self._servicio, tipo, params, self)
        self._hilo.progreso_actualizado.connect(self._al_progreso); self._hilo.senial_log.connect(self._registrar_log)
        self._hilo.proceso_completado.connect(self._al_exito); self._hilo.proceso_fallido.connect(self._al_error)
        self._hilo.finished.connect(lambda: self._restablecer_botones_cancelacion(True))
        self._hilo.start()

    def _al_progreso(self, actual: int, total: int, detalle: str) -> None:
        pct = int((actual / total) * 100) if total > 0 else 0
        self.barra_progreso.setValue(pct); self.banner.mostrar_en_proceso(f"[EN PROCESO] ({actual}/{total}) {detalle}")

    def _al_exito(self, mensaje: str, resultado: object) -> None:
        fue_cancelado, self._cancelando = self._cancelando, False
        self.btn_ejecutar.setEnabled(True); self.combo_flujo.setEnabled(True); self.btn_cancelar.setText("Detener")
        liberar_boton_protegido(self.btn_cancelar, habilitar=False); liberar_boton_protegido(self.btn_ejecutar, habilitar=True)
        if fue_cancelado:
            self.barra_progreso.setValue(0); self.banner.mostrar_info("[INFO] Tarea cancelada."); self._registrar_log("[INFO] Tarea cancelada.")
        elif mensaje.startswith("[ALERTA]"):
            self.banner.mostrar_advertencia(mensaje); self._registrar_log(mensaje)
        else:
            self.barra_progreso.setValue(100); self.banner.mostrar_exito(mensaje); self._registrar_log(mensaje)
        res_lista = resultado if isinstance(resultado, list) else ([resultado] if isinstance(resultado, FichaNegocioLens) else [])
        for item in res_lista: self._agregar_fila_tabla(item) if isinstance(item, FichaNegocioLens) else self._agregar_dict_tabla(item)

    def _al_error(self, error: str) -> None:
        self._cancelando = False; self.btn_ejecutar.setEnabled(True); self.combo_flujo.setEnabled(True)
        self.btn_cancelar.setText("Detener"); liberar_boton_protegido(self.btn_cancelar, habilitar=False)
        liberar_boton_protegido(self.btn_ejecutar, habilitar=True); self.banner.mostrar_error(f"[ERROR] {error}"); self._registrar_log(f"[ERROR] {error}")

    def _cancelar_proceso(self) -> None:
        if self._cancelando: return
        self._cancelando = True; self.btn_cancelar.setEnabled(False); self.btn_cancelar.setText("Cancelando...")
        self.banner.mostrar_en_proceso("[INFO] Cancelando tarea en curso...")
        if self._hilo is not None and self._hilo.isRunning():
            import threading; threading.Thread(target=self._hilo.cancelar, daemon=True).start()
            self._registrar_log("[INFO] Cancelando tarea en curso y cerrando navegador...")
        QTimer.singleShot(2500, self._restablecer_botones_cancelacion)

    def _restablecer_botones_cancelacion(self, forzar: bool = False) -> None:
        if not forzar and self._hilo is not None and self._hilo.isRunning():
            QTimer.singleShot(2500, lambda: self._restablecer_botones_cancelacion(True)); return
        self._cancelando = False; self.btn_cancelar.setText("Detener")
        liberar_boton_protegido(self.btn_cancelar, habilitar=False)
        liberar_boton_protegido(self.btn_ejecutar, habilitar=True); self.combo_flujo.setEnabled(True)

    def _registrar_log(self, mensaje: str) -> None: self.consola.agregar_log(mensaje)

    def _agregar_fila_tabla(self, f: FichaNegocioLens) -> None:
        for it in desglosar_ficha_por_telefono(f):
            r = self.tabla.rowCount(); self.tabla.insertRow(r)
            for c, v in enumerate((it.id_registro, it.estado_ia, it.propietario, it.negocio, it.categoria, it.telefono, it.ubicacion)):
                self.tabla.setItem(r, c, QTableWidgetItem(v))

    def _agregar_dict_tabla(self, it: dict) -> None:
        r = self.tabla.rowCount(); self.tabla.insertRow(r)
        vals = (str(it.get("id_registro", "")), str(it.get("estado_ia", "")), str(it.get("owner", it.get("propietario", ""))),
                str(it.get("negocio", "")), str(it.get("habla_espanol", it.get("categoria", ""))),
                str(it.get("telefonos", it.get("telefono", ""))), str(it.get("address", it.get("ubicacion", ""))))
        for c, v in enumerate(vals): self.tabla.setItem(r, c, QTableWidgetItem(v))

    def _cambiar_carpeta_salida(self) -> None:
        from procesos_ia.interfaz.comun.gestor_rutas_recientes import GestorRutasRecientes
        gr = GestorRutasRecientes(); d = gr.obtener_ruta_salida(self._carpeta_salida_custom or self._servicio.enrutador.extracciones)
        ruta = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Destino", d)
        if ruta: gr.guardar_ruta_salida(ruta); self._carpeta_salida_custom = Path(ruta); self._registrar_log(f"[INFO] Destino: {ruta}")

    def _abrir_carpeta_salida(self) -> None:
        s = (self._servicio.ultima_salida.parent if self._servicio.ultima_salida else (self._carpeta_salida_custom or self._servicio.enrutador.extracciones))
        s.mkdir(parents=True, exist_ok=True); os.startfile(str(s))

    def _limpiar_formulario(self) -> None:
        for p in (self.panel_modo_chat, self.panel_chat_imagenes, self.panel_archivo, self.panel_modo_ia_urls): p.limpiar()
        self.input_alt.clear(); self.tabla.setRowCount(0); self.barra_progreso.setValue(0); self.consola.limpiar()
        self.banner.mostrar_info("[INFO] Formulario restablecido.")

    def _al_volver(self) -> None: liberar_boton_protegido(self.btn_ejecutar, habilitar=True); self.volver_solicitado.emit()
    def adaptar_modo(self, modo: ModoPantalla) -> None:
        self.barra_acciones.adaptar_modo(modo)
        if hasattr(self, "lbl_guia_flujo"): self.lbl_guia_flujo.setText("[INFO] Modo IA / Lens" if modo == ModoPantalla.COMPACTO else "[INFO OPERACIÓN] Selecciona Modo IA o Google Lens.")

    @property
    def combo_plantillas(self) -> QComboBox: return self.panel_modo_chat.combo_plantillas
    @property
    def txt_instrucciones(self) -> object: return self.panel_modo_chat.txt_instrucciones
    @property
    def spin_lote(self) -> QSpinBox: return self.panel_modo_chat.spin_lote
