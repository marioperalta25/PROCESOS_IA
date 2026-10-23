"""Editor de criterios y resultados sin dependencia de archivos de entrada."""

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from procesos_ia.dominio.evaluaciones import DefinicionResultado, resultados_desde_datos
from procesos_ia.dominio.excepciones import ErrorProcesamiento
from procesos_ia.infraestructura.prompts.parametros import cargar_parametros_evaluacion


class EditorResultados(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._textos = cargar_parametros_evaluacion()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(6)
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
        agregar.clicked.connect(lambda: self.agregar())
        quitar.clicked.connect(self._quitar)
        acciones.addWidget(agregar)
        acciones.addWidget(quitar)
        layout.addLayout(acciones)

    def agregar(self, resultado: DefinicionResultado | None = None) -> None:
        fila = self.tabla.rowCount()
        self.tabla.insertRow(fila)
        valores = (
            resultado.clave if resultado else "",
            resultado.criterio if resultado else "",
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
        datos = []
        for fila in range(self.tabla.rowCount()):
            valores = [self.tabla.item(fila, c).text().strip() for c in range(self.tabla.columnCount())]
            tipo = self.tabla.cellWidget(fila, 3).currentText()
            vistas: set[str] = set()
            ops: list[str] = []
            for e in valores[4].split("|"):
                op = e.strip()
                if op and op.casefold() not in vistas:
                    vistas.add(op.casefold())
                    ops.append(op)
            if tipo != "texto":
                ops = []
            datos.append({
                "clave": valores[0], "criterio": valores[1],
                "entradas": [e.strip() for e in valores[2].split(",") if e.strip()],
                "tipo": tipo,
                "opciones": ops,
            })
        resultados = resultados_desde_datos(datos)
        if not resultados:
            raise ErrorProcesamiento(self._textos["plantilla_sin_resultados"])
        return resultados
