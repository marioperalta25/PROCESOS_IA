"""Activación de vistas integradas y composición diferida del chat."""

from pathlib import Path
from functools import partial
from PySide6.QtCore import QStandardPaths

from procesos_ia.aplicacion.conversacion import ServicioConversacion
from procesos_ia.infraestructura.ollama.parametros_chat import cargar_parametros_chat
from procesos_ia.infraestructura.ollama.chat import solicitar_chat
from procesos_ia.infraestructura.ollama.preparador_chat import PreparadorChatOllama
from procesos_ia.infraestructura.persistencia.repositorio_chat import RepositorioChat
from procesos_ia.interfaz.chat_hilo import HiloChat
from procesos_ia.interfaz.hilos import HiloCoordinadorTrabajo, HiloLiberarMemoria
from procesos_ia.interfaz.hilos_evaluacion import HiloMuestra, HiloRefinamiento
from procesos_ia.interfaz.responsivo import determinar_modo_pantalla
from procesos_ia.interfaz.vista_chat import VistaChat


class NavegacionVistas:
    def __init__(self, ventana) -> None:
        self.ventana = ventana
        self.chat = None
        self.vista_motores = None
        self.vista_ia_general = None
        self.parametros = cargar_parametros_chat()
        self._preparador = PreparadorChatOllama(ventana._cliente_ollama, self.parametros)

    def activar(self, vista) -> None:
        if hasattr(vista, "adaptar_modo"):
            vista.adaptar_modo(determinar_modo_pantalla(self.ventana.width()))
        self.ventana.pila_vistas.setCurrentWidget(vista)

    def ocupado(self) -> bool:
        tipos = (HiloChat, HiloCoordinadorTrabajo, HiloLiberarMemoria, HiloMuestra, HiloRefinamiento)
        return any(hilo.isRunning() for tipo in tipos for hilo in self.ventana.findChildren(tipo))

    def adaptar(self, ancho: int) -> None:
        ventana = self.ventana
        modo = determinar_modo_pantalla(ancho)
        for vista in (ventana.panel_encabezado, ventana.panel_archivos,
                      ventana.panel_configuracion, ventana.panel_telemetria,
                      ventana.panel_controles, ventana._vista_prompts,
                      ventana._vista_preparacion, self.chat, self.vista_motores,
                      self.vista_ia_general):
            if vista is not None:
                vista.adaptar_modo(modo)

    def abrir_motores(self) -> None:
        ventana = self.ventana
        if ventana._cierre.pendiente:
            return
        motor = getattr(ventana, "_motor_activo", "ollama")
        if self.vista_motores is None:
            from procesos_ia.interfaz.vista_motores import VistaConfiguracionMotores
            self.vista_motores = VistaConfiguracionMotores(
                motor, ventana._config_web, ventana,
            )
            self.vista_motores.volver_solicitado.connect(ventana._volver_a_principal)
            self.vista_motores.motor_configurado.connect(ventana._al_configurar_motor)
            self.vista_motores.ia_general_solicitado.connect(self.abrir_ia_general)
            self.vista_motores.plantillas_web_solicitadas.connect(self.abrir_prompts_web)
            ventana.pila_vistas.addWidget(self.vista_motores)
        else:
            self.vista_motores._motor_actual = motor
            self.vista_motores._sincronizar_desde_configuracion()
        self.activar(self.vista_motores)

    def abrir_prompts_web(self) -> None:
        ventana = self.ventana
        if ventana._cierre.pendiente:
            return
        ventana._abrir_dialogo_prompts()
        if getattr(ventana, "_vista_prompts", None) is not None:
            combo = ventana._vista_prompts.combo_filtro
            idx = combo.findData("ia_web")
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def abrir_ia_general(self) -> None:
        ventana = self.ventana
        if ventana._cierre.pendiente:
            return
        if self.vista_ia_general is None:
            from procesos_ia.interfaz.vista_ia_general import VistaIAGeneral
            self.vista_ia_general = VistaIAGeneral(
                configuracion_web=ventana._config_web,
                servicio_prompts=getattr(ventana, "_servicio_prompts", None),
                parent=ventana,
            )
            self.vista_ia_general.volver_solicitado.connect(
                lambda: self.activar(self.vista_motores)
            )
            ventana.pila_vistas.addWidget(self.vista_ia_general)
        self.activar(self.vista_ia_general)

    def permitir_inferencia(self) -> bool:
        if self.ocupado():
            self.ventana.panel_telemetria.agregar_log(self.parametros["textos"]["ocupado"])
            return False
        return True

    def abrir_chat(self) -> None:
        ventana = self.ventana
        if ventana._cierre.pendiente:
            return
        if self.chat is None:
            directorio = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
            repositorio = RepositorioChat(directorio / self.parametros["rutas"]["directorio"], self.parametros)
            generar = partial(solicitar_chat, ventana._cliente_ollama, parametros=self.parametros)
            servicio = ServicioConversacion(repositorio, generar, self.parametros, self._preparador.preparar)
            self.chat = VistaChat(servicio, self.parametros, self._opciones, self.ocupado, ventana,
                                  catalogo=self._catalogo)
            self.chat.volver_solicitado.connect(ventana._volver_a_principal)
            self.chat.solicitar_actualizacion_modelos.connect(
                lambda: ventana._actualizar_modelos_segundo_plano(auto_iniciar=True))
            ventana.pila_vistas.addWidget(self.chat)
        self.chat._pintar()
        self.activar(self.chat)

    def _opciones(self) -> tuple:
        panel = self.ventana.panel_configuracion
        return panel.modelo_seleccionado, panel.ventana_contexto, panel.temperatura

    def _catalogo(self) -> list[str]:
        combo = self.ventana.panel_configuracion.combo_modelos
        return [combo.itemData(i) for i in range(combo.count()) if combo.itemData(i)]

    def actualizar_catalogo(self) -> None:
        self._preparador.invalidar()
        if self.chat is not None:
            self.chat.servicio.estimador.limpiar()
            self.chat._selector.actualizar()
