"""Ventana principal de escritorio que coordina los paneles y flujos de trabajo."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from procesos_ia.aplicacion.coordinador import CoordinadorTrabajo
from procesos_ia.aplicacion.prompts import ServicioCatalogoPrompts
from procesos_ia.dominio.modelos import ConfiguracionTrabajo
from procesos_ia.dominio.prompts import PlantillaPrompt
from procesos_ia.infraestructura.ollama.cliente_http import ClienteHttpOllama
from procesos_ia.infraestructura.ollama.modelos import (
    DiagnosticoOllama,
    EstadoServicioOllama,
    InformacionModelo,
)
from procesos_ia.infraestructura.ollama.servicio_inferencia import (
    ServicioInferenciaOllama,
)
from procesos_ia.infraestructura.prompts.refinador_ollama import (
    RefinadorPromptOllama,
)
from procesos_ia.infraestructura.prompts.repositorio_md import (
    RepositorioPromptsMd,
)
from procesos_ia.interfaz.componentes.panel_archivos import PanelArchivos
from procesos_ia.interfaz.componentes.panel_configuracion import PanelConfiguracionIA
from procesos_ia.interfaz.componentes.panel_controles import PanelControles
from procesos_ia.interfaz.componentes.panel_encabezado import PanelEncabezado
from procesos_ia.interfaz.componentes.panel_telemetria import PanelTelemetria
from procesos_ia.interfaz.dialogo_prompt import DialogoGestionPrompts
from procesos_ia.interfaz.hilos import (
    HiloCoordinadorTrabajo,
    HiloDiagnosticoOllama,
    HiloLiberarMemoria,
)
from procesos_ia.interfaz.recursos import GestorRecursos
from procesos_ia.interfaz.tema import PaletaVisual, construir_hoja_estilos


class VentanaPrincipal(QMainWindow):
    """Ventana central que desacopla la presentación de la lógica de procesamiento."""

    def __init__(
        self,
        coordinador: CoordinadorTrabajo | None = None,
        cliente_ollama: ClienteHttpOllama | None = None,
        servicio_prompts: ServicioCatalogoPrompts | None = None,
        directorio_base: Path | None = None,
        directorio_prompts: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("PROCESOS_IA - Enriquecimiento Masivo de Datos")
        self.resize(840, 780)
        self.setMinimumSize(700, 600)

        self._paleta = PaletaVisual()
        self._recursos = GestorRecursos(directorio_base=directorio_base)
        self.setWindowIcon(self._recursos.obtener_icono_aplicacion())

        self._cliente_ollama = cliente_ollama or ClienteHttpOllama()
        self._coordinador = coordinador or CoordinadorTrabajo(
            servicio_inferencia=ServicioInferenciaOllama(self._cliente_ollama)
        )
        if servicio_prompts is not None:
            self._servicio_prompts = servicio_prompts
        else:
            dir_prompts = directorio_prompts or (Path.home() / "Desktop" / "procesos_ia_prompts")
            repo = RepositorioPromptsMd(dir_prompts)
            refinador = RefinadorPromptOllama(self._cliente_ollama)
            self._servicio_prompts = ServicioCatalogoPrompts(repo, refinador)

        self._hilo_trabajo: HiloCoordinadorTrabajo | None = None
        self._hilo_diagnostico: HiloDiagnosticoOllama | None = None
        self._hilo_memoria: HiloLiberarMemoria | None = None

        self._iniciar_ui()
        self._conectar_seniales()
        self.setStyleSheet(construir_hoja_estilos(self._paleta))

        # Diagnostico inicial de Ollama en segundo plano
        self._actualizar_diagnostico_ollama()
        self._cargar_catalogo_prompts()

    def _iniciar_ui(self) -> None:
        widget_central = QWidget(self)
        self.setCentralWidget(widget_central)

        layout_central = QVBoxLayout(widget_central)
        layout_central.setContentsMargins(12, 10, 12, 10)
        layout_central.setSpacing(8)

        # 1. Encabezado
        self.panel_encabezado = PanelEncabezado(self._recursos, self._paleta, self)
        layout_central.addWidget(self.panel_encabezado)

        # Contenedor desplazable para pantallas de menor resolucion
        area_scroll = QScrollArea(self)
        area_scroll.setWidgetResizable(True)
        area_scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        contenido_scroll = QWidget()
        layout_scroll = QVBoxLayout(contenido_scroll)
        layout_scroll.setContentsMargins(0, 0, 0, 0)
        layout_scroll.setSpacing(10)

        # 2. Archivos
        self.panel_archivos = PanelArchivos(self)
        layout_scroll.addWidget(self.panel_archivos)

        # 3. Configuracion de IA
        self.panel_configuracion = PanelConfiguracionIA(self)
        layout_scroll.addWidget(self.panel_configuracion)

        # 4. Telemetria
        self.panel_telemetria = PanelTelemetria(self._paleta, self)
        layout_scroll.addWidget(self.panel_telemetria)

        layout_scroll.addStretch()
        area_scroll.setWidget(contenido_scroll)
        layout_central.addWidget(area_scroll, stretch=1)

        # 5. Controles
        self.panel_controles = PanelControles(self)
        layout_central.addWidget(self.panel_controles)

    def _conectar_seniales(self) -> None:
        self.panel_encabezado.solicitar_actualizacion_ollama.connect(
            self._actualizar_diagnostico_ollama
        )
        self.panel_configuracion.solicitar_gestion_prompts.connect(
            self._abrir_dialogo_prompts
        )

        # Controles
        self.panel_controles.solicitar_iniciar.connect(self._iniciar_procesamiento)
        self.panel_controles.solicitar_pausa.connect(self._pausar_procesamiento)
        self.panel_controles.solicitar_reanudacion.connect(self._reanudar_procesamiento)
        self.panel_controles.solicitar_cancelacion.connect(self._cancelar_procesamiento)
        self.panel_controles.solicitar_liberar_memoria.connect(self._liberar_memoria_vram)

    def _actualizar_diagnostico_ollama(self) -> None:
        self.panel_telemetria.agregar_log("[INFO] Verificando servicio Ollama...")
        self._hilo_diagnostico = HiloDiagnosticoOllama(self._cliente_ollama, self)
        self._hilo_diagnostico.senial_diagnostico.connect(self._al_recibir_diagnostico)
        self._hilo_diagnostico.senial_error.connect(
            lambda err: self.panel_telemetria.agregar_log(f"[ERROR] Ollama: {err}")
        )
        self._hilo_diagnostico.start()

    def _al_recibir_diagnostico(
        self,
        diag: DiagnosticoOllama,
        modelos: list[InformacionModelo],
    ) -> None:
        self.panel_encabezado.actualizar_estado_ollama(diag)
        self.panel_configuracion.actualizar_modelos(modelos)
        self.panel_telemetria.agregar_log(f"[INFO] Diagnostico Ollama: {diag.mensaje}")
        if modelos:
            self.panel_telemetria.agregar_log(
                f"[INFO] {len(modelos)} modelo(s) disponible(s) en el sistema local"
            )

    def _cargar_catalogo_prompts(self) -> None:
        plantillas = self._servicio_prompts.listar_plantillas()
        self.panel_configuracion.actualizar_prompts(plantillas)

    def _abrir_dialogo_prompts(self) -> None:
        modelo = self.panel_configuracion.modelo_seleccionado
        dialogo = DialogoGestionPrompts(self._servicio_prompts, modelo, self)
        dialogo.plantilla_seleccionada.connect(self._al_seleccionar_plantilla)
        dialogo.exec()
        self._cargar_catalogo_prompts()

    def _al_seleccionar_plantilla(self, plantilla: PlantillaPrompt) -> None:
        self._cargar_catalogo_prompts()
        self.panel_telemetria.agregar_log(
            f"[INFO] Plantilla '{plantilla.titulo}' seleccionada para el trabajo"
        )

    def _iniciar_procesamiento(self) -> None:
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

        configuracion = ConfiguracionTrabajo(
            ruta_entrada=ruta_entrada,
            directorio_salida=self.panel_archivos.ruta_salida,
            nombre_modelo=modelo,
            tamano_lote=self.panel_configuracion.tamano_lote,
            limite_filas_particion=self.panel_configuracion.limite_particion,
            ventana_contexto=self.panel_configuracion.ventana_contexto,
            temperatura=self.panel_configuracion.temperatura,
            columnas_evaluar=tuple(columnas),
            prompt_sistema=self.panel_configuracion.prompt_sistema_seleccionado,
            formato_salida="csv",
        )

        self.panel_telemetria.reiniciar_indicadores()
        self.panel_controles.configurar_estado_ejecucion(en_ejecucion=True)

        self._hilo_trabajo = HiloCoordinadorTrabajo(self._coordinador, configuracion, self)
        self._hilo_trabajo.senial_progreso.connect(self.panel_telemetria.actualizar_progreso)
        self._hilo_trabajo.senial_fase_cambiada.connect(self.panel_telemetria.actualizar_fase)
        self._hilo_trabajo.senial_mensaje.connect(self.panel_telemetria.agregar_log)
        self._hilo_trabajo.senial_finalizado.connect(self._al_finalizar_trabajo)
        self._hilo_trabajo.senial_error.connect(self._al_fallar_trabajo)
        self._hilo_trabajo.start()

    def _pausar_procesamiento(self) -> None:
        if self._hilo_trabajo and self._hilo_trabajo.isRunning():
            self._hilo_trabajo.pausar()

    def _reanudar_procesamiento(self) -> None:
        if self._hilo_trabajo and self._hilo_trabajo.isRunning():
            self._hilo_trabajo.reanudar()

    def _cancelar_procesamiento(self) -> None:
        if self._hilo_trabajo and self._hilo_trabajo.isRunning():
            self._hilo_trabajo.cancelar()

    def _al_finalizar_trabajo(self, completado: bool, mensaje: str) -> None:
        self.panel_controles.configurar_estado_ejecucion(en_ejecucion=False)
        self.panel_telemetria.agregar_log(mensaje)
        if completado:
            QMessageBox.information(self, "Procesamiento Completado", mensaje)

    def _al_fallar_trabajo(self, mensaje_error: str) -> None:
        self.panel_controles.configurar_estado_ejecucion(en_ejecucion=False)
        self.panel_telemetria.agregar_log(mensaje_error)
        QMessageBox.critical(self, "Error de Ejecución", mensaje_error)

    def _liberar_memoria_vram(self) -> None:
        modelo = self.panel_configuracion.modelo_seleccionado
        if not modelo:
            QMessageBox.warning(self, "Modelo no seleccionado", "[ALERTA] Seleccione un modelo para descargar.")
            return

        self.panel_telemetria.agregar_log(f"[INFO] Solicitando descarga de memoria para '{modelo}'...")
        self._hilo_memoria = HiloLiberarMemoria(modelo, self._cliente_ollama, self)
        self._hilo_memoria.senial_resultado.connect(
            lambda _, msg: self.panel_telemetria.agregar_log(msg)
        )
        self._hilo_memoria.start()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._hilo_trabajo and self._hilo_trabajo.isRunning():
            resp = QMessageBox.question(
                self,
                "Proceso en ejecución",
                "Hay un procesamiento en curso. ¿Desea cancelar y salir?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if resp == QMessageBox.StandardButton.Yes:
                self._hilo_trabajo.cancelar()
                self._hilo_trabajo.wait(3000)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
