"""Copia completa de progreso: confirma lotes por ID y conserva las filas restantes."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from procesos_ia.aplicacion.comun.gestor_reanudacion_base import (
    COLUMNA_ESTADO, COLUMNA_FECHA, COLUMNA_ID, COLUMNA_MOTIVO,
    GestorReanudacionBase, identificar_fila,
)
from procesos_ia.aplicacion.comun.identidad_tabular import (
    IdentidadTabular, buscar_identidad, guardar_identidad, leer_identidad,
    marca_archivo, parametros_tabulares,
)
from procesos_ia.dominio.reanudacion import AccionReanudacion, EstadoIA, ResumenReanudacion
from procesos_ia.dominio.excepciones import ErrorPersistenciaTabular
from procesos_ia.infraestructura.archivos.escritor_csv import guardar_filas_csv
from procesos_ia.infraestructura.persistencia.bloqueo_trabajo import bloquear_trabajo


def limpiar_estados_antiguos(gestor: Any, modulo: str, parametros: dict) -> int:
    """Elimina subcarpetas .estado antiguas sin tocar el CSV final ni auditorias del usuario."""
    import shutil, time
    dias = int(parametros.get("dias_retencion_estado", 5))
    carpeta_estado = parametros.get("carpeta_estado", ".estado")
    if dias <= 0 or not carpeta_estado:
        return 0
    limite = time.time() - (dias * 86400)
    eliminados = 0
    for clave in ("completados", "fallidos", "cancelados"):
        raiz_estado = gestor.rama(modulo) / gestor.configuracion["estados"][clave]
        for dir_estado in raiz_estado.glob(f"*/{carpeta_estado}"):
            if not dir_estado.is_dir(): continue
            archivos = [a for a in dir_estado.iterdir() if a.is_file()]
            if not archivos or all(a.stat().st_mtime < limite for a in archivos):
                shutil.rmtree(dir_estado, ignore_errors=True)
                eliminados += 1
    return eliminados


def leer_progreso(ruta: Path, parametros: dict) -> list[dict[str, Any]]:
    """Un respaldo invalido debe dar un error, nunca convertirse en trabajo nuevo."""
    import csv, sys
    csv.field_size_limit(min(sys.maxsize, 10_000_000))
    try:
        with ruta.open(encoding="utf-8-sig", newline="") as archivo:
            lector = csv.DictReader(archivo, strict=True)
            if not lector.fieldnames or COLUMNA_ESTADO not in lector.fieldnames:
                raise ValueError(parametros["error_lectura"])
            filas = list(lector)
            if any(None in fila or any(v is None for v in fila.values()) for fila in filas):
                raise ValueError(parametros["error_lectura"])
            if any(f[COLUMNA_ESTADO] not in {e.value for e in EstadoIA} for f in filas):
                raise ValueError(parametros["error_lectura"])
            return filas
    except (OSError, UnicodeError, csv.Error) as error:
        raise ValueError(parametros["error_lectura"]) from error


class TrabajoTabular:
    """Estado de una ejecucion, transferible al hilo sin conexiones ni archivos abiertos."""

    def __init__(
        self, filas: list[dict[str, Any]], identidad: IdentidadTabular,
        respaldo: Path | None = None, filas_previas: list[dict[str, Any]] | None = None,
    ) -> None:
        self.identidad = identidad
        self.parametros = parametros_tabulares()
        self.respaldo = respaldo
        self._marca_respaldo = marca_archivo(respaldo) if respaldo else None
        self._originales = [dict(fila) for fila in filas]
        self.filas = []
        for indice, fila in enumerate(filas, 1):
            copia = dict(fila)
            copia[COLUMNA_ID] = identificar_fila(fila, indice, usar_id_externo=False)
            copia[COLUMNA_ESTADO] = EstadoIA.PENDIENTE.value
            copia[COLUMNA_MOTIVO] = copia[COLUMNA_FECHA] = ""
            self.filas.append(copia)
        self._indices = {f[COLUMNA_ID]: i for i, f in enumerate(self.filas)}
        if len(self._indices) != len(self.filas):
            raise ValueError(self.parametros["error_filas"])
        self._salida = None
        self._accion = AccionReanudacion.REPROCESAR_PENDIENTES_Y_FALLIDOS
        if filas_previas:
            self.filas = self._combinar(filas_previas)

    @property
    def resumen(self) -> ResumenReanudacion:
        registros = [GestorReanudacionBase.extraer_metadatos_fila(f, i) for i, f in enumerate(self.filas, 1)]
        resumen = GestorReanudacionBase.clasificar_registros(registros, self.identidad.origen or Path())
        resumen.ruta_respaldo = self.respaldo
        resumen.tiene_metadatos = resumen.tiene_metadatos or self.respaldo is not None
        return resumen

    def seleccionar(self, accion: AccionReanudacion) -> None:
        self._accion = accion
        if accion == AccionReanudacion.REINICIAR_TODO:
            self.respaldo = None
            self._marca_respaldo = None
            for indice, original in enumerate(self._originales):
                identificador = self.filas[indice][COLUMNA_ID]
                self.filas[indice] = {
                    **original, COLUMNA_ID: identificador, COLUMNA_ESTADO: EstadoIA.PENDIENTE.value,
                    COLUMNA_MOTIVO: "", COLUMNA_FECHA: "",
                }

    @property
    def filas_pendientes(self) -> list[dict[str, Any]]:
        if self._accion in (AccionReanudacion.CANCELAR, AccionReanudacion.RECUPERAR_RESULTADOS):
            return []
        estados = {EstadoIA.PENDIENTE}
        if self._accion != AccionReanudacion.SOLO_PENDIENTES:
            estados.update((EstadoIA.FALLIDO, EstadoIA.OMITIDO))
        return [dict(f) for f in self.filas if EstadoIA.normalizar(f.get(COLUMNA_ESTADO)) in estados]

    @property
    def solo_exportar(self) -> bool:
        return self._accion == AccionReanudacion.RECUPERAR_RESULTADOS

    def _combinar(self, cambios: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nuevas = list(self.filas)
        vistos = set()
        for fila in cambios:
            identificador = str(fila.get(COLUMNA_ID, "")).strip()
            if identificador not in self._indices or identificador in vistos:
                raise ValueError(self.parametros["error_filas"])
            if fila.get(COLUMNA_ESTADO) not in {estado.value for estado in EstadoIA}:
                raise ValueError(self.parametros["error_lectura"])
            vistos.add(identificador)
            indice = self._indices[identificador]
            nuevas[indice] = {**self._originales[indice], **fila, COLUMNA_ID: identificador}
        return nuevas

    @contextmanager
    def abrir(
        self, enrutador: Any, nombre_salida: str, carpeta_salida: Path | None = None,
        salida_existente: Any | None = None,
    ) -> Iterator[Any]:
        """Adquiere exclusion antes de mover o reservar carpetas; solo el hilo escribe."""
        gestor = enrutador.gestor_procesos(carpeta_salida)
        bloqueo = gestor.raiz / self.parametros["carpeta_bloqueos"] / self.identidad.huella
        with bloquear_trabajo(bloqueo, self.parametros["error_ocupado"]):
            limpiar_estados_antiguos(gestor, self.identidad.modulo, self.parametros)
            self.identidad.verificar_origen(self.parametros)
            if nombre_salida in (self.parametros["archivo_progreso"], self.parametros["archivo_identidad"]):
                raise ValueError(self.parametros["error_identidad"])
            if self.respaldo:
                if not self.respaldo.is_file() or marca_archivo(self.respaldo) != self._marca_respaldo:
                    raise ValueError(self.parametros["error_cambio"])
                ruta_meta = self.respaldo.parent / self.parametros["archivo_identidad"]
                if ruta_meta.exists():
                    datos = leer_identidad(ruta_meta, self.parametros)
                    if datos["huella"] != self.identidad.huella:
                        raise ValueError(self.parametros["error_identidad"])
                    nombre_salida = datos["archivo_salida"]
                else:
                    nombre_salida = self.respaldo.name
                dir_trabajo = self.respaldo.parent.parent if self.respaldo.parent.name == self.parametros.get("carpeta_estado", ".estado") else self.respaldo.parent
                salida = gestor.retomar(self.identidad.modulo, dir_trabajo / nombre_salida)
                if salida is None:
                    raise ValueError(self.parametros["error_identidad"])
            else:
                if salida_existente is not None and salida_existente.ruta.exists():
                    raise ValueError(self.parametros["error_identidad"])
                if self._accion != AccionReanudacion.REINICIAR_TODO:
                    if buscar_identidad(gestor, self.identidad, self.parametros):
                        raise ValueError(self.parametros["error_cambio"])
                salida = salida_existente or gestor.reservar(self.identidad.modulo, nombre_salida)
            self._salida = salida
            with salida:
                if self.identidad.origen and salida.ruta.resolve() == self.identidad.origen:
                    raise ValueError(self.parametros["error_origen"])
                guardar_identidad(salida.directorio, self.identidad, salida.nombre_archivo, self.parametros)
                self._guardar(self.filas)
                self._total_envio = len(self.filas_pendientes)
                yield salida

    def notificar_progreso(self, callback: Callable | None, procesadas: int, detalle: str) -> None:
        """Incluye el avance previo y cuenta solo filas confirmadas en esta ejecucion."""
        if callback:
            previo = len(self.filas) - self._total_envio
            callback(previo + procesadas, len(self.filas), detalle)

    def _guardar(self, filas: list[dict[str, Any]]) -> None:
        self.identidad.verificar_origen(self.parametros)
        try:
            dir_estado = self._salida.directorio / self.parametros.get("carpeta_estado", ".estado")
            dir_estado.mkdir(parents=True, exist_ok=True)
            guardar_filas_csv(filas, dir_estado / self.parametros["archivo_progreso"])
        except OSError as error:
            raise ErrorPersistenciaTabular(self.parametros["error_escritura"].format(causa=error)) from error

    def confirmar(self, cambios: list[dict[str, Any]]) -> None:
        """Solo anuncia el nuevo estado en memoria despues del reemplazo atomico en disco."""
        nuevas = self._combinar(cambios)
        self._guardar(nuevas)
        self.filas = nuevas

    def finalizar(self, estado: str, exportador: Callable = guardar_filas_csv) -> Path:
        """Exporta sin alterar el progreso canonico y mueve todos los archivos juntos."""
        if estado == "completados" and any(f[COLUMNA_ESTADO] != EstadoIA.EXITOSO.value for f in self.filas):
            estado = "fallidos"
        try:
            exportador(self.filas, self._salida.ruta)
        except OSError as error:
            raise ErrorPersistenciaTabular(self.parametros["error_exportacion"].format(causa=error)) from error
        return self._salida.finalizar(estado)
