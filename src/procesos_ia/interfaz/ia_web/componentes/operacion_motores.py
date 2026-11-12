"""Construccion del panel de entradas y acciones para los motores web."""

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from procesos_ia.interfaz.ia_web.componentes.panel_archivo_general import PanelArchivoGeneral
from procesos_ia.interfaz.ia_web.conversacional.panel_modo_chat_imagenes import PanelModoChatImagenes
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido


def construir_operacion_motores(vista) -> None:
    lay = QVBoxLayout(vista.tab_operacion); lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(6)

    lay_op = QHBoxLayout(); vista.lbl_operacion = QLabel("Operación Web:", vista); lay_op.addWidget(vista.lbl_operacion)
    vista.combo_operacion = QComboBox(vista)
    for t, d in (("Procesamiento por Lotes de Texto (CSV con delimitador '|')", "csv_texto"),
                 ("Extracción de Imágenes (1 a 1 - Carpeta con campos estructurados)", "extraccion_negocios_imagenes"),
                 ("Carpeta de Imágenes", "carpeta_imagenes")):
        vista.combo_operacion.addItem(t, d)
    vista.combo_operacion.currentIndexChanged.connect(vista._al_cambiar_operacion)
    vista.check_auditoria_md = QCheckBox("Generar auditoría (.md)", vista)
    vista.check_auditoria_md.setChecked(getattr(vista._config_web, "generar_auditoria_md", True))
    lay_op.addWidget(vista.combo_operacion, stretch=1)
    lay_op.addWidget(vista.check_auditoria_md)

    vista.btn_iniciar_sesion = QPushButton("Iniciar Sesión / Abrir Navegador", vista)
    vista.btn_iniciar_sesion.setToolTip("Abre Chromium en la carpeta aislada de motores para ingresar credenciales")
    conectar_boton_protegido(
        vista.btn_iniciar_sesion, vista._abrir_navegador_manual,
        "[INFO] Abriendo navegador para inicio de sesión...", 800,
    )
    lay_op.addWidget(vista.btn_iniciar_sesion)
    lay.addLayout(lay_op)

    # Panel especializado 1 a 1 con casillas (negocio, telefonos, owner, address, habla_espanol)
    nom_ini = "Google Gemini Web" if getattr(vista, "_motor_actual", "gemini") == "gemini" else "DeepSeek Web"
    vista.panel_imagenes_1a1 = PanelModoChatImagenes(vista._servicio_proc._enrutador, vista, nombre_modulo=nom_ini)
    vista.panel_imagenes_1a1.log_notificado.connect(vista.consola.agregar_log)
    vista.panel_imagenes_1a1.setVisible(False)
    lay.addWidget(vista.panel_imagenes_1a1)

    vista.panel_archivo = PanelArchivoGeneral(vista, enrutador=vista._servicio_proc._enrutador, nombre_modulo=nom_ini)
    lay.addWidget(vista.panel_archivo)

    # Plantillas e instrucciones
    vista.grupo_prompt = QGroupBox("Instrucciones de Evaluación (Prompt)", vista)
    lay_p = QVBoxLayout(vista.grupo_prompt); lay_p.setContentsMargins(6, 4, 6, 4); lay_p.setSpacing(4)
    lay_top = QHBoxLayout(); lay_top.addWidget(QLabel("Plantilla IA Web:", vista))
    vista.combo_plantillas = QComboBox(vista)
    vista.combo_plantillas.currentIndexChanged.connect(vista._al_seleccionar_plantilla)
    vista.btn_plantillas_ia_web = QPushButton("Gestionar Plantillas (|)", vista)
    conectar_boton_protegido(
        vista.btn_plantillas_ia_web, vista.plantillas_web_solicitadas.emit,
        "[INFO] Abriendo plantillas IA Web...", 600,
    )
    lay_top.addWidget(vista.combo_plantillas, stretch=1); lay_top.addWidget(vista.btn_plantillas_ia_web); lay_p.addLayout(lay_top)

    from procesos_ia.interfaz.componentes.editor_texto_expandible import EditorTextoExpandible
    vista.txt_instrucciones = EditorTextoExpandible(placeholder="Instrucciones para DeepSeek o Gemini...", parent=vista)
    lay_p.addWidget(vista.txt_instrucciones); lay.addWidget(vista.grupo_prompt)

    vista.widget_opts = QWidget(vista)
    lay_opts = QHBoxLayout(vista.widget_opts); lay_opts.setContentsMargins(0, 0, 0, 0)
    vista.spin_lote, vista.spin_rotacion = QSpinBox(vista), QSpinBox(vista)
    vista.spin_lote.setRange(1, 30); vista.spin_lote.setValue(5)
    vista.spin_rotacion.setRange(1, 50); vista.spin_rotacion.setValue(2)
    vista.input_imagenes = QLineEdit(vista); vista.input_imagenes.setVisible(False)
    vista.grupo_directo = vista.panel_imagenes_1a1
    lay_opts.addWidget(QLabel("Filas por lote:", vista))
    lay_opts.addWidget(vista.spin_lote)
    lay_opts.addSpacing(16)
    lay_opts.addWidget(QLabel("Rotar chat cada (lotes):", vista))
    lay_opts.addWidget(vista.spin_rotacion)
    lay_opts.addStretch()
    lay.addWidget(vista.widget_opts)

    vista.barra_progreso = QProgressBar(vista); vista.barra_progreso.setRange(0, 100); vista.barra_progreso.setValue(0)
    lay.addWidget(vista.barra_progreso)

    lay_btns = QHBoxLayout()
    vista.btn_ejecutar = QPushButton("Iniciar Procesamiento Web", vista); vista.btn_ejecutar.setMinimumHeight(32)
    conectar_boton_protegido(vista.btn_ejecutar, vista._ejecutar_procesamiento_web, "[INFO] Iniciando...", 800)
    vista.btn_cancelar = QPushButton("Detener", vista); vista.btn_cancelar.setEnabled(False)
    conectar_boton_protegido(vista.btn_cancelar, vista._cancelar_procesamiento, tiempo_bloqueo_ms=0, auto_desbloquear=False)
    vista.btn_abrir_salida, vista.btn_ia_general = QPushButton("Abrir Carpeta de Salida", vista), QPushButton("IA General (Google Lens / Modo IA)", vista)
    conectar_boton_protegido(vista.btn_abrir_salida, vista._abrir_carpeta_salida, tiempo_bloqueo_ms=800)
    conectar_boton_protegido(vista.btn_ia_general, vista.ia_general_solicitado.emit, tiempo_bloqueo_ms=800)
    for b, s in ((vista.btn_ejecutar, 2), (vista.btn_cancelar, 1), (vista.btn_abrir_salida, 1), (vista.btn_ia_general, 1)):
        lay_btns.addWidget(b, stretch=s)
    lay.addLayout(lay_btns); vista._al_cambiar_operacion()
