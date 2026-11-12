"""Dialogo modal nativo para resolucion de reanudacion y reproceso granular."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from procesos_ia.dominio.reanudacion import AccionReanudacion, ResumenReanudacion
from procesos_ia.interfaz.protector_botones import ProtectorBotones


class DialogoReanudacionEstado(QDialog):
    """Ventana flotante modal estilizada con proteccion antirebote en botones."""

    def __init__(
        self,
        resumen: ResumenReanudacion,
        parent: QWidget | None = None,
        es_carpeta_imagenes: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Diagnóstico de Reanudación de Proceso")
        self.setModal(True)
        self.setMinimumWidth(520)

        self._resumen = resumen
        self._es_imagenes = es_carpeta_imagenes
        self._accion_seleccionada = AccionReanudacion.CANCELAR
        self._protector = ProtectorBotones(parent=self)

        self._construir_ui()

    @property
    def accion(self) -> AccionReanudacion:
        """Accion seleccionada por el usuario."""
        return self._accion_seleccionada

    def _construir_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Encabezado
        lbl_titulo = QLabel("<b>Avance previo detectado</b>", self)
        lbl_titulo.setStyleSheet("font-size: 14px; color: #1E293B;")
        layout.addWidget(lbl_titulo)

        tipo_str = "carpeta de imágenes" if self._es_imagenes else "archivo de datos"
        nom_origen = self._resumen.origen.name
        lbl_desc = QLabel(
            f"El sistema detectó registros procesados para este {tipo_str} (<b>{nom_origen}</b>). "
            "Revise el balance actual y seleccione cómo desea continuar:",
            self,
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #475569; font-size: 12px;")
        layout.addWidget(lbl_desc)

        # Panel de Metricas
        marco_metricas = QFrame(self)
        marco_metricas.setStyleSheet(
            "QFrame { background-color: #F8FAFC; border: 1px solid #E2E8F0; "
            "border-radius: 6px; padding: 10px; }"
        )
        layout_m = QVBoxLayout(marco_metricas)
        layout_m.setSpacing(6)

        txt_total = f"• Total de registros evaluados: <b>{self._resumen.total}</b>"
        txt_exit = f"• <span style='color: #16A34A;'>Exitosos:</span> <b>{self._resumen.exitosos}</b>"
        txt_fall = (
            f"• <span style='color: #DC2626;'>Fallidos / Omitidos:</span> "
            f"<b>{self._resumen.total_reintentables}</b>"
        )
        txt_pend = f"• <span style='color: #CA8A04;'>Pendientes:</span> <b>{self._resumen.pendientes}</b>"

        layout_m.addWidget(QLabel(txt_total, marco_metricas))
        layout_m.addWidget(QLabel(txt_exit, marco_metricas))
        layout_m.addWidget(QLabel(txt_fall, marco_metricas))
        layout_m.addWidget(QLabel(txt_pend, marco_metricas))
        layout.addWidget(marco_metricas)

        # Botonera de Acciones
        layout_botones = QVBoxLayout()
        layout_botones.setSpacing(8)

        # Boton 1: Reprocesar pendientes y fallidos (Recomendado si hay fallos o pendientes)
        if self._resumen.total_reintentables > 0 or self._resumen.pendientes > 0:
            btn_recuperar = QPushButton(
                f"[RECOMENDADO] Procesar Pendientes y Recuperar Fallidos ({self._resumen.total_reintentables + self._resumen.pendientes})",
                self,
            )
            btn_recuperar.setStyleSheet(
                "QPushButton { background-color: #2563EB; color: white; font-weight: bold; "
                "padding: 8px 14px; border-radius: 5px; }"
                "QPushButton:hover { background-color: #1D4ED8; }"
            )
            self._protector.vincular(
                btn_recuperar,
                lambda: self._finalizar(AccionReanudacion.REPROCESAR_PENDIENTES_Y_FALLIDOS),
            )
            layout_botones.addWidget(btn_recuperar)

        # Boton 2: Solo procesar pendientes (si aplica)
        if self._resumen.pendientes > 0:
            btn_pendientes = QPushButton(
                f"Procesar Únicamente Pendientes Nuevos ({self._resumen.pendientes})", self
            )
            btn_pendientes.setStyleSheet(
                "QPushButton { background-color: #0D9488; color: white; padding: 7px 12px; border-radius: 5px; }"
                "QPushButton:hover { background-color: #0F766E; }"
            )
            self._protector.vincular(
                btn_pendientes, lambda: self._finalizar(AccionReanudacion.SOLO_PENDIENTES)
            )
            layout_botones.addWidget(btn_pendientes)

        # Botones inferiores (Reiniciar y Cancelar)
        layout_inferior = QHBoxLayout()
        btn_reiniciar = QPushButton("Reiniciar Todo desde Cero", self)
        btn_reiniciar.setStyleSheet(
            "QPushButton { background-color: #EF4444; color: white; padding: 6px 12px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #DC2626; }"
        )
        self._protector.vincular(
            btn_reiniciar, lambda: self._finalizar(AccionReanudacion.REINICIAR_TODO)
        )

        btn_cancelar = QPushButton("Cancelar", self)
        btn_cancelar.setStyleSheet(
            "QPushButton { background-color: #E2E8F0; color: #334155; padding: 6px 12px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #CBD5E1; }"
        )
        self._protector.vincular(
            btn_cancelar, lambda: self._finalizar(AccionReanudacion.CANCELAR)
        )

        layout_inferior.addWidget(btn_reiniciar)
        layout_inferior.addStretch()
        layout_inferior.addWidget(btn_cancelar)
        layout_botones.addLayout(layout_inferior)

        layout.addLayout(layout_botones)

    def _finalizar(self, accion: AccionReanudacion) -> None:
        self._accion_seleccionada = accion
        self.accept() if accion != AccionReanudacion.CANCELAR else self.reject()


def solicitar_decision_reanudacion(
    resumen: ResumenReanudacion,
    parent: QWidget | None = None,
    es_carpeta_imagenes: bool = False,
) -> AccionReanudacion:
    """Invoca el dialogo modal y devuelve la accion seleccionada."""
    dialogo = DialogoReanudacionEstado(
        resumen=resumen, parent=parent, es_carpeta_imagenes=es_carpeta_imagenes
    )
    dialogo.exec()
    return dialogo.accion
