"""Ventana principal de escritorio que coordina los paneles y flujos de trabajo."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QCloseEvent, QResizeEvent
from PySide6.QtWidgets import QMainWindow, QMessageBox, QWidget

from procesos_ia.aplicacion.coordinador import CoordinadorTrabajo
from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
from procesos_ia.dominio.modelos import ConfiguracionTrabajo
from procesos_ia.dominio.prompts import PlantillaPrompt
from procesos_ia.infraestructura.ollama.cache_modelos import CacheModelosOllama
from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.ollama.modelos import DiagnosticoOllama, EstadoServicioOllama, InformacionModelo
from procesos_ia.infraestructura.ollama.servicio_inferencia import ServicioInferenciaOllama
from procesos_ia.infraestructura.prompts.refinador_ollama import RefinadorPromptOllama
from procesos_ia.infraestructura.prompts.repositorio_md import RepositorioPromptsMd
from procesos_ia.infraestructura.web.configuracion_web import ConfiguracionWeb
from procesos_ia.interfaz.borradores import GestorBorradores
from procesos_ia.interfaz.cierre import CierreCooperativo
from procesos_ia.interfaz.composicion_ventana import construir_paneles
from procesos_ia.interfaz.dialogo_prompt import DialogoGestionPrompts
from procesos_ia.interfaz.dialogo_preparacion import DialogoPrepararTrabajo
from procesos_ia.interfaz.hilos import HiloCoordinadorTrabajo, HiloDiagnosticoOllama, HiloLiberarMemoria, HiloListarModelos
from procesos_ia.interfaz.recursos import GestorRecursos
from procesos_ia.interfaz.navegacion import NavegacionVistas
from procesos_ia.interfaz.protector_botones import establecer_notificador_predeterminado
from procesos_ia.interfaz.tema import PaletaVisual, construir_hoja_estilos


class VentanaPrincipal(QMainWindow):
    """Ventana central que desacopla la presentación de la lógica de procesamiento."""

    def __init__(
        self, coordinador: CoordinadorTrabajo | None = None, cliente_ollama: ClienteHttpOllama | None = None,
        servicio_prompts: ServicioCatalogoPrompts | None = None, directorio_base: Path | None = None,
        directorio_prompts: Path | None = None, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("PROCESOS_IA - Enriquecimiento Masivo de Datos")
        self.resize(840, 780)
        self.setMinimumSize(700, 600)

        self._paleta = PaletaVisual()
        self._recursos = GestorRecursos(directorio_base=directorio_base)
        self.setWindowIcon(self._recursos.obtener_icono_aplicacion())

        self._cliente_ollama = cliente_ollama or ClienteHttpOllama()
        self._servicio_inferencia = ServicioInferenciaOllama(self._cliente_ollama)
        self._coordinador_inyectado = coordinador
        self._enrutador = EnrutadorSalidas()
        self._enrutador.asegurar_directorios(); self._enrutador.migrar_plantillas_previas()
        dir_p = directorio_prompts or self._enrutador.plantillas
        self._servicio_prompts = servicio_prompts or ServicioCatalogoPrompts(
            RepositorioPromptsMd(dir_p), RefinadorPromptOllama(self._cliente_ollama)
        )

        self._cierre = CierreCooperativo(self)
        self._gestor_borradores = GestorBorradores()
        self._vista_prompts: DialogoGestionPrompts | None = None
        self._vista_preparacion: DialogoPrepararTrabajo | None = None
        self._consulta_activa, self._config_web = False, ConfiguracionWeb()
        self._motor_activo = "ollama"
        self._hilo_trabajo = self._hilo_diagnostico = self._hilo_memoria = self._hilo_modelos = None
        ruta_cache = (directorio_base / ".cache_modelos.json") if directorio_base else None
        self._cache_modelos = CacheModelosOllama(ruta_archivo=ruta_cache)

        self._iniciar_ui()
        self._navegacion = NavegacionVistas(self)
        self.panel_encabezado.solicitar_chat.connect(self._navegacion.abrir_chat)
        self._conectar_seniales()
        self.setStyleSheet(construir_hoja_estilos(self._paleta))

        modelos_previos = self._cache_modelos.cargar()
        if modelos_previos: self.panel_configuracion.actualizar_modelos(modelos_previos)
        self._actualizar_modelos_segundo_plano(); self._cargar_catalogo_prompts()

    def _iniciar_ui(self) -> None:
        construir_paneles(self, self._recursos, self._paleta)

    def _conectar_seniales(self) -> None:
        for s in (self.panel_encabezado.solicitar_actualizacion_ollama, self.panel_configuracion.solicitar_actualizacion_modelos):
            s.connect(lambda: self._actualizar_modelos_segundo_plano(auto_iniciar=True))

        for senial, slot in (
            (self.panel_configuracion.solicitar_gestion_prompts, self._abrir_dialogo_prompts),
            (self.panel_encabezado.solicitar_configuracion_motores, self._navegacion.abrir_motores),
            (self.panel_controles.solicitar_iniciar, self._iniciar_procesamiento),
            (self.panel_controles.solicitar_pausa, self._pausar_procesamiento),
            (self.panel_controles.solicitar_reanudacion, self._reanudar_procesamiento),
            (self.panel_controles.solicitar_cancelacion, self._cancelar_procesamiento),
            (self.panel_controles.solicitar_liberar_memoria, self._liberar_memoria_vram),
        ):
            senial.connect(slot)
        establecer_notificador_predeterminado(self.panel_telemetria.agregar_log)

    def _actualizar_modelos_segundo_plano(self, auto_iniciar: bool = False) -> None:
        if self._consulta_activa or self._cierre.pendiente:
            return
        self._consulta_activa = True
        if self._hilo_modelos is not None:
            self._hilo_modelos.deleteLater()
        self.panel_configuracion.btn_refrescar_modelos.setEnabled(False)
        self.panel_encabezado.btn_refrescar.setEnabled(False)
        self.panel_telemetria.agregar_log("[INFO] Consultando modelos en Ollama...")
        self._hilo_modelos = HiloListarModelos(
            self._cliente_ollama, auto_iniciar=auto_iniciar, tiempo_limite=3.0, parent=self
        )
        self._hilo_modelos.senial_modelos.connect(self._al_recibir_modelos)
        self._hilo_modelos.senial_mensaje.connect(self.panel_telemetria.agregar_log)
        self._hilo_modelos.senial_error.connect(self._al_fallar_modelos)
        self._hilo_modelos.finished.connect(self._al_terminar_consulta_modelos)
        self._hilo_modelos.start()

    def _al_terminar_consulta_modelos(self) -> None:
        self._consulta_activa = False
        self.panel_configuracion.btn_refrescar_modelos.setEnabled(True)
        self.panel_encabezado.btn_refrescar.setEnabled(True)

    def _al_recibir_modelos(self, modelos: list[InformacionModelo]) -> None:
        self.panel_configuracion.actualizar_modelos(modelos)
        self._navegacion.actualizar_catalogo()
        self._cache_modelos.guardar(modelos)
        diag = DiagnosticoOllama(
            estado=EstadoServicioOllama.DISPONIBLE, version_cliente=None, version_servidor="activa",
            ruta_ejecutable=None, url_base=self._cliente_ollama.url_base,
            mensaje=f"Servicio Ollama disponible ({len(modelos)} modelos)",
        )
        self.panel_encabezado.actualizar_estado_ollama(diag)
        self.panel_telemetria.agregar_log(f"[INFO] {len(modelos)} modelo(s) disponible(s) en el sistema local")

    def _al_fallar_modelos(self, error: str) -> None:
        if self._navegacion.chat is not None: self._navegacion.chat.banner.mostrar_error(error)
        self.panel_telemetria.agregar_log(f"[ALERTA] {error}")
        diag = DiagnosticoOllama(
            estado=EstadoServicioOllama.ERROR_CONEXION, version_cliente=None, version_servidor=None,
            ruta_ejecutable=None, url_base=self._cliente_ollama.url_base, mensaje=error,
        )
        self.panel_encabezado.actualizar_estado_ollama(diag)

    def _cargar_catalogo_prompts(self) -> None:
        self.panel_configuracion.actualizar_prompts(self._servicio_prompts.listar_plantillas())

    def _abrir_dialogo_prompts(self) -> None:
        modelo = self.panel_configuracion.modelo_seleccionado
        if self._vista_prompts is None:
            self._vista_prompts = DialogoGestionPrompts(
                self._servicio_prompts, modelo, self._gestor_borradores, self,
            )
            self._vista_prompts.volver_solicitado.connect(self._volver_a_principal)
            self._vista_prompts.plantilla_seleccionada.connect(self._al_seleccionar_plantilla)
            self.pila_vistas.addWidget(self._vista_prompts)
        else:
            self._vista_prompts._modelo_activo = modelo
            self._vista_prompts.restaurar_borrador_si_existe()
        self._vista_prompts.btn_refinar.setEnabled(not self._navegacion.ocupado())
        self._navegacion.activar(self._vista_prompts)

    def _volver_a_principal(self) -> None:
        self.pila_vistas.setCurrentWidget(self.vista_principal)
        self._cargar_catalogo_prompts()

    def _al_seleccionar_plantilla(self, plantilla: PlantillaPrompt) -> None:
        self._cargar_catalogo_prompts()
        indice = self.panel_configuracion.combo_prompts.findData(plantilla.identificador)
        self.panel_configuracion.combo_prompts.setCurrentIndex(indice)
        self.panel_telemetria.agregar_log(f"[INFO] Plantilla '{plantilla.titulo}' seleccionada")

    def _iniciar_procesamiento(self) -> None:
        if self._cierre.pendiente or not self._navegacion.permitir_inferencia():
            return
        ruta_entrada = self.panel_archivos.ruta_entrada
        if not ruta_entrada or not ruta_entrada.is_file():
            QMessageBox.warning(self, "Archivo requerido", "[ALERTA] Debe seleccionar un archivo tabular válido.")
            return

        columnas = self.panel_archivos.obtener_columnas_seleccionadas()
        if not columnas:
            QMessageBox.warning(self, "Columnas requeridas", "[ALERTA] Debe seleccionar al menos una columna a evaluar.")
            return

        modelo = self.panel_configuracion.modelo_seleccionado
        if not modelo:
            QMessageBox.warning(self, "Modelo requerido", "[ALERTA] Debe seleccionar un modelo de Ollama.")
            return

        p_cfg, p_arch = self.panel_configuracion, self.panel_archivos
        configuracion = ConfiguracionTrabajo(
            ruta_entrada=ruta_entrada, directorio_salida=p_arch.ruta_salida,
            nombre_modelo=modelo, tamano_lote=p_cfg.tamano_lote,
            limite_filas_particion=p_cfg.limite_particion, ventana_contexto=p_cfg.ventana_contexto,
            temperatura=p_cfg.temperatura, tiempo_limite_lote_segundos=p_cfg.tiempo_limite_lote_segundos,
            columnas_evaluar=tuple(columnas), prompt_sistema=p_cfg.prompt_sistema_seleccionado,
            formato_salida="csv", columnas_salida_modelo=p_cfg.columnas_salida_modelo,
            carpeta_imagenes=None, rotacion_chat_cada=1, modo_procesamiento="lote",
        )

        plantilla = self.panel_configuracion.plantilla_seleccionada
        if plantilla is None:
            QMessageBox.warning(self, "Plantilla requerida", "Seleccione una plantilla con criterios y resultados.")
            return

        if self._vista_preparacion is not None:
            self.pila_vistas.removeWidget(self._vista_preparacion); self._vista_preparacion.deleteLater()

        self._vista_preparacion = DialogoPrepararTrabajo(
            configuracion, plantilla, self.panel_archivos.encabezados, self._servicio_inferencia,
            self._gestor_borradores, self,
        )
        self._vista_preparacion.volver_solicitado.connect(self._volver_a_principal)
        self._vista_preparacion.trabajo_confirmado.connect(self._al_confirmar_trabajo)
        self._vista_preparacion.restaurar_borrador_si_existe()
        self.pila_vistas.addWidget(self._vista_preparacion); self._navegacion.activar(self._vista_preparacion)

    def _obtener_servicio_inferencia(self):
        return self._servicio_inferencia

    def _al_configurar_motor(self, tipo: str, cfg_web: ConfiguracionWeb) -> None:
        self._config_web = cfg_web
        self.panel_telemetria.agregar_log(f"[INFO] Configuración de IA Web guardada: {tipo}")

    def _al_confirmar_trabajo(self, configuracion: ConfiguracionTrabajo) -> None:
        if self._cierre.pendiente or not self._navegacion.permitir_inferencia():
            return
        self.pila_vistas.setCurrentWidget(self.vista_principal)
        self.panel_telemetria.reiniciar_indicadores()
        self.panel_controles.configurar_estado_ejecucion(en_ejecucion=True)

        self._hilo_trabajo = HiloCoordinadorTrabajo(
            configuracion=configuracion, coordinador=self._coordinador_inyectado,
            servicio_inferencia=self._obtener_servicio_inferencia(), parent=self,
        )
        for s, sl in ((self._hilo_trabajo.senial_progreso, self.panel_telemetria.actualizar_progreso),
                      (self._hilo_trabajo.senial_fase_cambiada, self.panel_telemetria.actualizar_fase),
                      (self._hilo_trabajo.senial_mensaje, self.panel_telemetria.agregar_log),
                      (self._hilo_trabajo.senial_finalizado, self._al_finalizar_trabajo),
                      (self._hilo_trabajo.senial_error, self._al_fallar_trabajo)):
            s.connect(sl)
        self._hilo_trabajo.start()

    def _pausar_procesamiento(self) -> None:
        if self._hilo_trabajo and self._hilo_trabajo.isRunning(): self._hilo_trabajo.pausar()

    def _reanudar_procesamiento(self) -> None:
        if self._hilo_trabajo and self._hilo_trabajo.isRunning(): self._hilo_trabajo.reanudar()

    def _cancelar_procesamiento(self) -> None:
        if self._hilo_trabajo and self._hilo_trabajo.isRunning(): self._hilo_trabajo.cancelar()

    def _al_finalizar_trabajo(self, completado: bool, mensaje: str) -> None:
        self.panel_controles.configurar_estado_ejecucion(en_ejecucion=False)
        self.panel_telemetria.agregar_log(mensaje)
        if completado and not self._cierre.pendiente:
            QMessageBox.information(self, "Completado", mensaje)

    def _al_fallar_trabajo(self, err: str) -> None:
        self.panel_controles.configurar_estado_ejecucion(en_ejecucion=False)
        self.panel_telemetria.agregar_log(err)
        if not self._cierre.pendiente: QMessageBox.critical(self, "Error", err)

    def _liberar_memoria_vram(self) -> None:
        if self._cierre.pendiente or not self._navegacion.permitir_inferencia(): return
        modelo = self.panel_configuracion.modelo_seleccionado
        if not modelo:
            QMessageBox.warning(self, "Modelo requerido", "[ALERTA] Seleccione un modelo.")
            return
        self.panel_telemetria.agregar_log(f"[INFO] Descargando memoria de '{modelo}'...")
        if self._hilo_memoria is not None: self._hilo_memoria.deleteLater()
        self._hilo_memoria = HiloLiberarMemoria(modelo, self._cliente_ollama, self)
        self._hilo_memoria.senial_resultado.connect(lambda _, msg: self.panel_telemetria.agregar_log(msg))
        self._hilo_memoria.start()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event); self._navegacion.adaptar(event.size().width())

    def closeEvent(self, event: QCloseEvent) -> None:
        if (not self._cierre.pendiente and self._hilo_trabajo and self._hilo_trabajo.isRunning()):
            resp = QMessageBox.question(self, "Proceso en ejecución", "¿Desea cancelar el trabajo?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp != QMessageBox.StandardButton.Yes:
                event.ignore(); return
        establecer_notificador_predeterminado(None)
        self._cierre.solicitar(event, self.findChildren(QThread))
