"""Tablero de telemetría ligero (< 10 MB) para supervisión en tiempo real."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from procesos_ia.interfaz.tema import PaletaVisual


class PanelTelemetria(QGroupBox):
    """Monitor de recursos ligero que supervisa filas, velocidad, RAM y bitácora."""

    def __init__(
        self,
        paleta: PaletaVisual | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("3. Tablero de Telemetría y Rendimiento Local", parent)
        self._paleta = paleta or PaletaVisual()

        self._iniciar_ui()

    def _iniciar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 1. Fila de estado de fase y barra de progreso
        layout_fase = QHBoxLayout()
        self.label_fase_titulo = QLabel("Estado del proceso:", self)
        layout_fase.addWidget(self.label_fase_titulo)

        self.label_fase = QLabel("[EN REPOSO]", self)
        self.label_fase.setObjectName("estado_pill")
        self.label_fase.setStyleSheet(
            f"background-color: {self._paleta.fondo_resaltado}; color: {self._paleta.texto_principal}; "
            f"border: 1px solid {self._paleta.borde_control}; border-radius: 10px; font-weight: bold; padding: 2px 8px;"
        )
        layout_fase.addWidget(self.label_fase)
        layout_fase.addStretch()
        layout.addLayout(layout_fase)

        self.barra_progreso = QProgressBar(self)
        self.barra_progreso.setRange(0, 100)
        self.barra_progreso.setValue(0)
        self.barra_progreso.setTextVisible(True)
        layout.addWidget(self.barra_progreso)

        # 2. Metricas cuantitativas en grilla
        layout_metricas = QGridLayout()
        layout_metricas.setHorizontalSpacing(16)
        layout_metricas.setVerticalSpacing(4)

        layout_metricas.addWidget(QLabel("Progreso de filas:", self), 0, 0)
        self.val_filas = QLabel("0 / 0 (0%)", self)
        self.val_filas.setStyleSheet("font-weight: 600;")
        layout_metricas.addWidget(self.val_filas, 0, 1)

        layout_metricas.addWidget(QLabel("Velocidad:", self), 0, 2)
        self.val_velocidad = QLabel("0.0 filas/s", self)
        self.val_velocidad.setStyleSheet("font-weight: 600;")
        layout_metricas.addWidget(self.val_velocidad, 0, 3)

        layout_metricas.addWidget(QLabel("Consumo RAM proceso:", self), 1, 0)
        self.val_ram = QLabel("0.0 MB", self)
        self.val_ram.setStyleSheet("font-weight: 600;")
        layout_metricas.addWidget(self.val_ram, 1, 1)

        layout_metricas.addWidget(QLabel("Salud de hardware:", self), 1, 2)
        self.val_salud = QLabel("[OPTIMA]", self)
        self.val_salud.setStyleSheet(f"font-weight: 600; color: {self._paleta.exito};")
        layout_metricas.addWidget(self.val_salud, 1, 3)

        layout.addLayout(layout_metricas)

        # 3. Bitacora acotada (evita consumo mayor a 10 MB manteniendo maximo 60 bloques)
        self.label_bitacora = QLabel("Registro de eventos y confirmaciones WAL:", self)
        layout.addWidget(self.label_bitacora)

        self.texto_bitacora = QPlainTextEdit(self)
        self.texto_bitacora.setReadOnly(True)
        self.texto_bitacora.setMaximumBlockCount(60)
        self.texto_bitacora.setMaximumHeight(85)
        self.texto_bitacora.setStyleSheet(
            f"background-color: {self._paleta.superficie}; font-family: Consolas, monospace; font-size: 8.5pt;"
        )
        layout.addWidget(self.texto_bitacora)

    def actualizar_fase(self, fase: str) -> None:
        """Actualiza el indicador de fase con el color adecuado según la salud."""
        self.label_fase.setText(fase)
        if "[EN PROCESO]" in fase:
            color = self._paleta.accion_principal
            bg = "#FCEEEA"
        elif "[COMPLETADO]" in fase:
            color = self._paleta.exito
            bg = "#E2ECE8"
        elif "[PAUSADO]" in fase:
            color = self._paleta.advertencia
            bg = "#F8F1E5"
        elif "[ERROR]" in fase or "[CANCELADO]" in fase:
            color = self._paleta.error
            bg = "#F9EBEB"
        else:
            color = self._paleta.texto_principal
            bg = self._paleta.fondo_resaltado

        self.label_fase.setStyleSheet(
            f"background-color: {bg}; color: {color}; border: 1px solid {color}; "
            "border-radius: 10px; font-weight: bold; padding: 2px 8px;"
        )

    def actualizar_progreso(
        self,
        procesadas: int,
        totales: int,
        ram_mb: float,
        velocidad: float,
    ) -> None:
        """Actualiza los medidores numéricos y la barra de progreso."""
        if totales > 0:
            porcentaje = int((procesadas / totales) * 100)
            self.barra_progreso.setValue(porcentaje)
            self.val_filas.setText(f"{procesadas:,} / {totales:,} ({porcentaje}%)")
        else:
            self.barra_progreso.setValue(0)
            self.val_filas.setText(f"{procesadas:,} / Desconocido")

        self.val_velocidad.setText(f"{velocidad:.1f} filas/s")
        self.val_ram.setText(f"{ram_mb:.1f} MB")

        # Cuidar el presupuesto de hardware (< 500 MB para el proceso, alerta si sube)
        if ram_mb > 500.0:
            self.val_salud.setText("[ALERTA MEMORIA]")
            self.val_salud.setStyleSheet(f"font-weight: 600; color: {self._paleta.advertencia};")
        else:
            self.val_salud.setText("[OPTIMA]")
            self.val_salud.setStyleSheet(f"font-weight: 600; color: {self._paleta.exito};")

    def agregar_log(self, mensaje: str) -> None:
        """Agrega una línea a la bitácora manteniendo la rotación circular."""
        self.texto_bitacora.appendPlainText(mensaje)
        sb = self.texto_bitacora.verticalScrollBar()
        sb.setValue(sb.maximum())

    def reiniciar_indicadores(self) -> None:
        """Restaura los valores iniciales para un nuevo lote o archivo."""
        self.barra_progreso.setValue(0)
        self.val_filas.setText("0 / 0 (0%)")
        self.val_velocidad.setText("0.0 filas/s")
        self.actualizar_fase("[EN REPOSO]")
