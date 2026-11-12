"""Dialogo modal especializado para decisiones de checkpoint en carpetas de imagenes."""

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

from procesos_ia.aplicacion.comun.gestor_checkpoint_imagenes import (
    EstadoCheckpointCarpeta,
)
from procesos_ia.interfaz.protector_botones import ProtectorBotones


class DialogoCheckpointImagenes(QDialog):
    """Ventana modal interactiva con diagnostico de avance y decision de archivo de salida."""

    def __init__(
        self,
        estado: EstadoCheckpointCarpeta,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Diagnóstico de Memoria de Imágenes")
        self.setModal(True)
        self.setMinimumWidth(540)

        self._estado = estado
        self._accion: str = "cancelar"
        self._anexar_en_anterior: bool = False
        self._protector = ProtectorBotones(parent=self)

        self._construir_ui()

    @property
    def resultado(self) -> tuple[str, bool]:
        """Tupla con (accion_elegida, anexar_en_archivo_anterior)."""
        return self._accion, self._anexar_en_anterior

    def _construir_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        lbl_titulo = QLabel("<b>Memoria previa de carpeta detectada</b>", self)
        lbl_titulo.setStyleSheet("font-size: 14px; color: #1E293B;")
        layout.addWidget(lbl_titulo)

        n_fall = len(self._estado.fallidas)
        n_nuev = len(self._estado.nuevas)
        n_exit = len(self._estado.exitosas)
        n_tot = self._estado.total_disco

        motor_previo = (self._estado.ultimo_motor or self._estado.modulo).upper()
        motor_actual = self._estado.modulo.upper()

        if self._estado.es_otro_motor:
            aviso_motor = (
                f"La carpeta <b>{self._estado.carpeta.name}</b> fue evaluada previamente con <b>[{motor_previo}]</b>.<br>"
                f"<span style='color: #2563EB;'><b>[INFO] ¿Desea continuar con [{motor_actual}] desde donde lo dejó [{motor_previo}]?</b></span>"
            )
        else:
            aviso_motor = f"La carpeta <b>{self._estado.carpeta.name}</b> ya fue evaluada anteriormente en <b>{motor_actual}</b>."

        desc_txt = (
            f"{aviso_motor}<br>"
            f"Diagnóstico: <b>{n_exit}</b> exitosas previas, "
            f"<b>{n_fall}</b> con fallas/sin respuesta y "
            f"<b>{n_nuev}</b> nuevas agregadas recientemente."
        )
        lbl_desc = QLabel(desc_txt, self)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #475569; font-size: 12px;")
        layout.addWidget(lbl_desc)

        # Panel de Estado del Archivo Anterior
        marco_archivo = QFrame(self)
        marco_archivo.setStyleSheet(
            "QFrame { background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px; }"
        )
        lay_arc = QVBoxLayout(marco_archivo)
        lay_arc.setSpacing(4)

        if self._estado.csv_anterior_existe and self._estado.ruta_csv_anterior:
            lay_arc.addWidget(QLabel(f"• Archivo anterior: <span style='color: #16A34A;'><b>[OK] Localizado en disco</b></span>", marco_archivo))
            lay_arc.addWidget(QLabel(f"<span style='font-size: 11px; color: #64748B;'>{self._estado.ruta_csv_anterior}</span>", marco_archivo))
        elif self._estado.ruta_csv_anterior:
            lay_arc.addWidget(QLabel(f"• Archivo anterior: <span style='color: #DC2626;'><b>[NO LOCALIZADO]</b> (fue movido o eliminado)</span>", marco_archivo))
            lay_arc.addWidget(QLabel(f"<span style='font-size: 11px; color: #94A3B8;'>Ruta previa: {self._estado.ruta_csv_anterior}</span>", marco_archivo))
        else:
            lay_arc.addWidget(QLabel("• Archivo anterior: <i>No registrado en checkpoint</i>", marco_archivo))

        layout.addWidget(marco_archivo)

        # Botonera de Opciones
        lay_botones = QVBoxLayout()
        lay_botones.setSpacing(8)

        total_pend = n_fall + n_nuev

        # Si el archivo anterior existe en disco
        if self._estado.csv_anterior_existe and total_pend > 0:
            txt_anexar = (
                f"[RECOMENDADO] Continuar en Archivo Anterior ({motor_previo}) (Modo Append)"
                if self._estado.es_otro_motor
                else f"[RECOMENDADO] Anexar {total_pend} pendientes al Archivo Anterior (Modo Append)"
            )
            btn_anexar = QPushButton(txt_anexar, self)
            btn_anexar.setStyleSheet(
                "QPushButton { background-color: #2563EB; color: white; font-weight: bold; padding: 8px 14px; border-radius: 5px; }"
                "QPushButton:hover { background-color: #1D4ED8; }"
            )
            self._protector.vincular(btn_anexar, lambda: self._resolver("reprocesar_pendientes_y_fallidas", True))
            lay_botones.addWidget(btn_anexar)

            txt_nuevo = (
                f"Continuar con {motor_actual} en un Nuevo Archivo CSV"
                if self._estado.es_otro_motor
                else f"Procesar {total_pend} pendientes en un Nuevo Archivo CSV"
            )
            btn_nuevo = QPushButton(txt_nuevo, self)
            btn_nuevo.setStyleSheet(
                "QPushButton { background-color: #0D9488; color: white; font-weight: 500; padding: 7px 12px; border-radius: 5px; }"
                "QPushButton:hover { background-color: #0F766E; }"
            )
            self._protector.vincular(btn_nuevo, lambda: self._resolver("reprocesar_pendientes_y_fallidas", False))
            lay_botones.addWidget(btn_nuevo)

        # Si el archivo anterior NO existe en disco (Fallback)
        elif not self._estado.csv_anterior_existe and total_pend > 0:
            txt_fb = (
                f"Continuar con {motor_actual} en un Nuevo Archivo CSV ({total_pend} pendientes)"
                if self._estado.es_otro_motor
                else f"Continuar con {total_pend} pendientes en un Nuevo Archivo CSV"
            )
            btn_fallback = QPushButton(txt_fb, self)
            btn_fallback.setStyleSheet(
                "QPushButton { background-color: #2563EB; color: white; font-weight: bold; padding: 8px 14px; border-radius: 5px; }"
                "QPushButton:hover { background-color: #1D4ED8; }"
            )
            self._protector.vincular(btn_fallback, lambda: self._resolver("reprocesar_pendientes_y_fallidas", False))
            lay_botones.addWidget(btn_fallback)

        # Si solo hay nuevas
        if n_nuev > 0 and n_fall > 0 and self._estado.csv_anterior_existe:
            btn_solo_nuevas = QPushButton(
                f"Procesar Únicamente las {n_nuev} Fotos Nuevas",
                self,
            )
            btn_solo_nuevas.setStyleSheet(
                "QPushButton { background-color: #475569; color: white; padding: 6px 12px; border-radius: 5px; }"
                "QPushButton:hover { background-color: #334155; }"
            )
            self._protector.vincular(btn_solo_nuevas, lambda: self._resolver("solo_nuevas", True))
            lay_botones.addWidget(btn_solo_nuevas)

        # Botones inferiores (Reiniciar y Cancelar)
        lay_inf = QHBoxLayout()
        txt_reiniciar = f"Reiniciar Todo desde Cero ({motor_actual})" if self._estado.es_otro_motor else "Reiniciar Todo desde Cero"
        btn_reiniciar = QPushButton(txt_reiniciar, self)
        btn_reiniciar.setStyleSheet(
            "QPushButton { background-color: #EF4444; color: white; padding: 6px 12px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #DC2626; }"
        )
        self._protector.vincular(btn_reiniciar, lambda: self._resolver("reiniciar_todo", False))

        btn_cancelar = QPushButton("Cancelar", self)
        btn_cancelar.setStyleSheet(
            "QPushButton { background-color: #E2E8F0; color: #334155; padding: 6px 12px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #CBD5E1; }"
        )
        self._protector.vincular(btn_cancelar, lambda: self._resolver("cancelar", False))

        lay_inf.addWidget(btn_reiniciar)
        lay_inf.addStretch()
        lay_inf.addWidget(btn_cancelar)
        lay_botones.addLayout(lay_inf)

        layout.addLayout(lay_botones)

    def _resolver(self, accion: str, anexar: bool) -> None:
        self._accion = accion
        self._anexar_en_anterior = anexar
        if accion != "cancelar":
            self.accept()
        else:
            self.reject()


def solicitar_decision_checkpoint_imagenes(
    estado: EstadoCheckpointCarpeta,
    parent: QWidget | None = None,
) -> tuple[str, bool]:
    """Abre el diálogo modal y devuelve (accion, anexar_en_archivo_anterior)."""
    dialogo = DialogoCheckpointImagenes(estado=estado, parent=parent)
    dialogo.exec()
    return dialogo.resultado
