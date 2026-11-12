"""Especializacion para deteccion y reanudacion de carpetas de imagenes.

Consumido por Google Lens, Gemini Imagenes y DeepSeek Imagenes.
"""

from __future__ import annotations

from pathlib import Path

from procesos_ia.aplicacion.comun.gestor_reanudacion_base import GestorReanudacionBase
from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.aplicacion.ia_web.comun.gestor_lote_imagenes import (
    buscar_csv_previo_carpeta,
    listar_imagenes_carpeta,
)
from procesos_ia.dominio.reanudacion import (
    AccionReanudacion,
    EstadoIA,
    RegistroEstado,
    ResumenReanudacion,
)


class GestorReanudacionImagenes(GestorReanudacionBase):
    """Subclase especializada en el flujo de imagenes 1 a 1."""

    def __init__(self, enrutador: EnrutadorSalidas) -> None:
        self._enrutador = enrutador

    def evaluar_carpeta(
        self, carpeta: Path, modulo: str = "imagenes", prefijo: str = "extraccion_lens"
    ) -> tuple[list[RegistroEstado], ResumenReanudacion]:
        """Audita una carpeta de fotos cotejando su CSV incremental existente."""
        imagenes = listar_imagenes_carpeta(carpeta)
        total_fotos = len(imagenes)
        if total_fotos == 0:
            return [], ResumenReanudacion(origen=carpeta)

        gestor = self._enrutador.gestor_procesos()
        base_modulo = gestor.rama(modulo)
        csv_previo = buscar_csv_previo_carpeta(base_modulo, carpeta.name, prefijo)

        mapa_previo: dict[str, RegistroEstado] = {}
        if csv_previo and csv_previo.is_file():
            regs_csv, _ = self.inspeccionar_csv(csv_previo)
            for r in regs_csv:
                nom = Path(r.id_registro).name.lower()
                mapa_previo[nom] = r

        registros_consolidados: list[RegistroEstado] = []
        for idx, img in enumerate(imagenes, start=1):
            nom_foto = img.name.lower()
            if nom_foto in mapa_previo:
                reg_existente = mapa_previo[nom_foto]
                registros_consolidados.append(reg_existente)
            else:
                registros_consolidados.append(
                    RegistroEstado(
                        id_registro=img.name,
                        estado=EstadoIA.PENDIENTE,
                        motivo="No iniciado",
                        datos_originales={"ruta_imagen": str(img)},
                    )
                )

        resumen = self.clasificar_registros(registros_consolidados, carpeta)
        resumen.ruta_respaldo = csv_previo
        return registros_consolidados, resumen

    @classmethod
    def filtrar_imagenes(
        cls,
        carpeta: Path,
        registros_evaluados: list[RegistroEstado],
        accion: AccionReanudacion,
    ) -> list[Path]:
        """Obtiene la lista concreta de rutas de imagenes a procesar segun la accion."""
        imagenes_disco = {img.name.lower(): img for img in listar_imagenes_carpeta(carpeta)}

        if accion == AccionReanudacion.REINICIAR_TODO or not registros_evaluados:
            return list(imagenes_disco.values())

        filtrados = cls.filtrar_por_accion(registros_evaluados, accion)
        rutas_finales: list[Path] = []
        for reg in filtrados:
            nom = Path(reg.id_registro).name.lower()
            if nom in imagenes_disco:
                rutas_finales.append(imagenes_disco[nom])

        return rutas_finales
