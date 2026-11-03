"""Editor de criterios y resultados sin dependencia de archivos de entrada."""

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from procesos_ia.dominio.evaluaciones import DefinicionResultado, resultados_desde_datos
from procesos_ia.dominio.normalizador import sanear_identificador_columna
from procesos_ia.infraestructura.prompts.parametros import cargar_parametros_evaluacion
from procesos_ia.interfaz.protector_botones import conectar_boton_protegido


class EditorResultados(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._textos = cargar_parametros_evaluacion()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(6)

        lbl_titulo = QLabel("Columnas Estructuradas en CSV (Opcional):", self)
        lbl_titulo.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_titulo)

        lbl_ayuda = QLabel(
            "[INFO] Define qué columnas fijas creará el sistema en el CSV para campos específicos. "
            "Si dejas esta tabla vacía, el sistema autodescubrirá dinámicamente cualquier campo que la IA responda.",
            self,
        )
        lbl_ayuda.setWordWrap(True)
        lbl_ayuda.setStyleSheet("color: #58615B; font-size: 11px;")
        layout.addWidget(lbl_ayuda)

        self.tabla = QTableWidget(0, len(self._textos["columnas_editor"]), self)
        self.tabla.setMinimumHeight(120)
        self.tabla.setMaximumHeight(200)
        self.tabla.setHorizontalHeaderLabels(self._textos["columnas_editor"])
        self.tabla.horizontalHeader().setStretchLastSection(True)
        for columna, parametro in enumerate((
            "ancho_resultado_editor", "ancho_criterio_editor", "ancho_entradas_editor", "ancho_tipo_editor",
        )):
            self.tabla.setColumnWidth(columna, self._textos[parametro])
        layout.addWidget(self.tabla)
        acciones = QHBoxLayout()
        agregar = QPushButton(self._textos["agregar"], self)
        quitar = QPushButton(self._textos["eliminar"], self)
        agregar.setMinimumHeight(28)
        quitar.setMinimumHeight(28)
        conectar_boton_protegido(
            agregar, lambda: self.agregar(), "[INFO] Agregando nueva evaluación...", tiempo_bloqueo_ms=400,
        )
        conectar_boton_protegido(
            quitar, self._quitar, "[INFO] Eliminando evaluación seleccionada...", tiempo_bloqueo_ms=400,
        )
        acciones.addWidget(agregar)
        acciones.addWidget(quitar)
        layout.addLayout(acciones)

    def agregar(self, resultado: DefinicionResultado | None = None) -> None:
        fila = self.tabla.rowCount()
        self.tabla.insertRow(fila)
        clave_defecto = f"resultado_{fila + 1}"
        criterio_defecto = "Evaluación de registro"
        valores = (
            resultado.clave if resultado else clave_defecto,
            resultado.criterio if resultado else criterio_defecto,
            ", ".join(resultado.entradas) if resultado else "datos",
            resultado.tipo if resultado else self._textos["tipos_editor"][0],
            " | ".join(resultado.opciones) if resultado else "",
        )
        for columna, valor in enumerate(valores):
            item = QTableWidgetItem(valor)
            item.setToolTip(valor)
            self.tabla.setItem(fila, columna, item)
        tipo = QComboBox(self.tabla)
        tipo.addItems(self._textos["tipos_editor"])
        tipo.setCurrentText(valores[3])
        self.tabla.setCellWidget(fila, 3, tipo)
        self.tabla.resizeRowToContents(fila)

    def _quitar(self) -> None:
        fila = self.tabla.currentRow()
        if fila >= 0:
            self.tabla.removeRow(fila)

    def cargar(self, resultados: tuple[DefinicionResultado, ...]) -> None:
        self.tabla.setRowCount(0)
        for resultado in resultados:
            self.agregar(resultado)

    def obtener(self) -> tuple[DefinicionResultado, ...]:
        if self.tabla.rowCount() == 0:
            return ()
        datos = []
        for fila in range(self.tabla.rowCount()):
            valores = [
                self.tabla.item(fila, c).text().strip() if self.tabla.item(fila, c) is not None else ""
                for c in range(self.tabla.columnCount())
            ]
            widget = self.tabla.cellWidget(fila, 3)
            tipo = widget.currentText() if isinstance(widget, QComboBox) else "texto"
            vistas: set[str] = set()
            ops: list[str] = []
            opciones_str = valores[4] if len(valores) > 4 else ""
            for e in opciones_str.split("|"):
                op = e.strip()
                if op and op.casefold() not in vistas:
                    vistas.add(op.casefold())
                    ops.append(op)
            if tipo != "texto":
                ops = []
            clave_cruda = valores[0] if len(valores) > 0 and valores[0] else f"resultado_{fila + 1}"
            clave_limpia = sanear_identificador_columna(clave_cruda, prefijo=f"resultado_{fila + 1}")
            criterio_crudo = valores[1] if len(valores) > 1 and valores[1] else f"Evaluación de {clave_limpia}"
            entradas_crudas = valores[2] if len(valores) > 2 else ""
            entradas_limpias = [e.strip() for e in entradas_crudas.split(",") if e.strip()] or ["datos"]
            datos.append({
                "clave": clave_limpia, "criterio": criterio_crudo,
                "entradas": entradas_limpias,
                "tipo": tipo,
                "opciones": ops,
            })
        return resultados_desde_datos(datos)
