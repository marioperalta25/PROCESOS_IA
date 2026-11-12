"""Gestor centralizado de checkpoints persistentes para procesamiento de imagenes.

Proporciona deteccion O(1), registro de memoria por carpeta, rastreo de salidas CSV
y clasificacion precisa de imagenes exitosas, fallidas y nuevas para todos los motores.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from procesos_ia.aplicacion.enrutador_salidas import EnrutadorSalidas
from procesos_ia.dominio.reanudacion import EstadoIA

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EstadoCheckpointCarpeta:
    """Diagnostico consolidado del estado de procesamiento de una carpeta de imagenes."""

    carpeta: Path
    modulo: str
    es_nueva: bool
    total_disco: int
    exitosas: list[Path] = field(default_factory=list)
    fallidas: list[Path] = field(default_factory=list)
    nuevas: list[Path] = field(default_factory=list)
    ruta_csv_anterior: Path | None = None
    csv_anterior_existe: bool = False
    fecha_ultimo_proceso: str = ""
    ultimo_motor: str = ""

    @property
    def total_pendientes_o_fallidas(self) -> int:
        """Cantidad total de imagenes pendientes por procesar o recuperar."""
        return len(self.fallidas) + len(self.nuevas)

    @property
    def requiere_decision(self) -> bool:
        """Determina si amerita consultar al usuario por existir avance previo o pendientes."""
        if self.es_nueva:
            return False
        return len(self.exitosas) > 0 or self.total_pendientes_o_fallidas > 0

    @property
    def es_otro_motor(self) -> bool:
        """Determina si el checkpoint fue generado por un motor diferente al solicitante."""
        if not self.ultimo_motor:
            return False
        return self.ultimo_motor.lower().strip() != self.modulo.lower().strip()


class GestorCheckpointImagenes:
    """Administra checkpoints en archivos JSON O(1) universales y compartidos entre motores."""

    def __init__(self, enrutador: EnrutadorSalidas | None = None) -> None:
        self._enrutador = enrutador or EnrutadorSalidas()
        self._dir_checkpoints = self._enrutador.raiz / ".checkpoints_imagenes"
        self._dir_checkpoints.mkdir(parents=True, exist_ok=True)

    def _generar_id_carpeta(self, carpeta: Path, modulo: str = "") -> str:
        """Genera un identificador universal unico para la carpeta, compartido por todos los motores."""
        ruta_abs = str(carpeta.resolve()).lower()
        hash_ruta = hashlib.sha256(ruta_abs.encode("utf-8")).hexdigest()[:12]
        nom_seguro = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in carpeta.name)
        return f"carpeta_{nom_seguro}_{hash_ruta}.json"

    def _obtener_ruta_checkpoint(self, carpeta: Path, modulo: str = "") -> Path:
        ruta_universal = self._dir_checkpoints / self._generar_id_carpeta(carpeta)
        if ruta_universal.is_file():
            return ruta_universal

        nom_seguro = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in carpeta.name)
        ruta_abs = str(carpeta.resolve()).lower()
        hash_ruta = hashlib.sha256(ruta_abs.encode("utf-8")).hexdigest()[:12]
        for m in (modulo.lower().strip(), "gemini", "deepseek", "modo_ia", "imagenes"):
            if not m:
                continue
            ruta_antigua = self._dir_checkpoints / f"{m}_{nom_seguro}_{hash_ruta}.json"
            if ruta_antigua.is_file():
                try:
                    ruta_antigua.replace(ruta_universal)
                    return ruta_universal
                except Exception:
                    return ruta_antigua

        return ruta_universal

    def evaluar_carpeta(self, carpeta: Path, modulo: str = "general") -> EstadoCheckpointCarpeta:
        """Evalua el estado real de la carpeta contra su checkpoint persistente."""
        from procesos_ia.aplicacion.ia_web.comun.gestor_lote_imagenes import (
            listar_imagenes_carpeta,
        )
        imagenes_disco = listar_imagenes_carpeta(carpeta)
        total_disco = len(imagenes_disco)
        modulo_norm = modulo.lower().strip()
        ruta_cp = self._obtener_ruta_checkpoint(carpeta, modulo_norm)

        if not ruta_cp.is_file() or ruta_cp.stat().st_size == 0:
            return EstadoCheckpointCarpeta(
                carpeta=carpeta,
                modulo=modulo_norm,
                es_nueva=True,
                total_disco=total_disco,
                nuevas=imagenes_disco,
            )

        try:
            with open(ruta_cp, "r", encoding="utf-8") as f:
                datos_cp = json.load(f)
        except Exception as error:
            logger.warning("[ALERTA] No se pudo leer checkpoint de %s: %s", carpeta.name, error)
            return EstadoCheckpointCarpeta(
                carpeta=carpeta,
                modulo=modulo_norm,
                es_nueva=True,
                total_disco=total_disco,
                nuevas=imagenes_disco,
            )

        raw_csv = datos_cp.get("ultima_salida_csv")
        ruta_csv = Path(raw_csv) if raw_csv else None
        csv_existe = bool(ruta_csv and ruta_csv.is_file())

        mapa_imgs: dict[str, dict[str, Any]] = datos_cp.get("imagenes", {})
        exitosas: list[Path] = []
        fallidas: list[Path] = []
        nuevas: list[Path] = []

        for img in imagenes_disco:
            clave_foto = img.name.lower()
            info_foto = mapa_imgs.get(clave_foto) or mapa_imgs.get(img.stem.lower())
            if not info_foto:
                nuevas.append(img)
                continue

            estado_str = str(info_foto.get("estado", "")).upper()
            if "EXITOS" in estado_str or "OK" in estado_str:
                exitosas.append(img)
            else:
                fallidas.append(img)

        ultimo_m = str(datos_cp.get("ultimo_motor") or datos_cp.get("ultimo_modulo") or "")
        return EstadoCheckpointCarpeta(
            carpeta=carpeta,
            modulo=modulo_norm,
            es_nueva=False,
            total_disco=total_disco,
            exitosas=exitosas,
            fallidas=fallidas,
            nuevas=nuevas,
            ruta_csv_anterior=ruta_csv,
            csv_anterior_existe=csv_existe,
            fecha_ultimo_proceso=str(datos_cp.get("fecha_actualizacion", "")),
            ultimo_motor=ultimo_m,
        )

    def actualizar_checkpoint(
        self,
        carpeta: Path,
        modulo: str,
        resultados_procesados: list[dict[str, Any]],
        ruta_salida_csv: Path | None = None,
    ) -> Path:
        """Actualiza o fusiona atomicamente el avance en el checkpoint de la carpeta."""
        modulo_norm = modulo.lower().strip()
        ruta_cp = self._obtener_ruta_checkpoint(carpeta, modulo_norm)

        datos_existentes: dict[str, Any] = {}
        if ruta_cp.is_file():
            try:
                with open(ruta_cp, "r", encoding="utf-8") as f:
                    datos_existentes = json.load(f)
            except Exception:
                datos_existentes = {}

        mapa_imgs: dict[str, dict[str, Any]] = datos_existentes.get("imagenes", {})

        for r in resultados_procesados:
            nom_foto = str(r.get("archivo_imagen") or r.get("fuente_imagen") or r.get("id_registro") or "").strip()
            if not nom_foto:
                continue
            nom_archivo = Path(nom_foto).name.lower()
            estado_raw = str(r.get("estado_ia") or r.get("estado") or "PENDIENTE").upper()
            estado_norm = EstadoIA.normalizar(estado_raw).value

            negocio_val = str(r.get("negocio") or r.get("nombre_negocio") or "").strip()
            if negocio_val.lower() == "json":
                negocio_val = "ND"

            mapa_imgs[nom_archivo] = {
                "estado": estado_norm,
                "fecha": datetime.now().isoformat(timespec="seconds"),
                "negocio": negocio_val,
                "telefonos": r.get("telefonos", []),
            }

        nueva_ruta_csv = str(ruta_salida_csv.resolve()) if ruta_salida_csv else datos_existentes.get("ultima_salida_csv")

        estructura = {
            "nombre_carpeta": carpeta.name,
            "ruta_absoluta_carpeta": str(carpeta.resolve()),
            "ultimo_modulo": modulo_norm,
            "ultimo_motor": modulo_norm,
            "ultima_salida_csv": nueva_ruta_csv,
            "fecha_actualizacion": datetime.now().isoformat(timespec="seconds"),
            "imagenes": mapa_imgs,
        }

        import time
        dir_check = ruta_cp.parent
        dir_check.mkdir(parents=True, exist_ok=True)
        temp_cp = dir_check / f".tmp_{ruta_cp.stem}_{time.time_ns()}.json"
        try:
            with open(temp_cp, "w", encoding="utf-8") as f:
                json.dump(estructura, f, indent=2, ensure_ascii=False)
            reemplazado = False
            for intento in range(5):
                try:
                    temp_cp.replace(ruta_cp)
                    reemplazado = True
                    break
                except OSError:
                    time.sleep(0.04 * (intento + 1))
            if not reemplazado:
                with open(ruta_cp, "w", encoding="utf-8") as f:
                    json.dump(estructura, f, indent=2, ensure_ascii=False)
        except Exception as error:
            logger.error("[ERROR] Fallo al escribir checkpoint de %s: %s", carpeta.name, error)
        finally:
            if temp_cp.exists():
                try:
                    temp_cp.unlink(missing_ok=True)
                except OSError:
                    pass

        return ruta_cp

    def reiniciar_checkpoint(self, carpeta: Path, modulo: str = "") -> bool:
        """Elimina el checkpoint existente para iniciar un procesamiento desde cero."""
        modulo_norm = modulo.lower().strip()
        ruta_cp = self._obtener_ruta_checkpoint(carpeta, modulo_norm)
        if ruta_cp.is_file():
            try:
                ruta_cp.unlink(missing_ok=True)
            except OSError:
                pass

        nom_seguro = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in carpeta.name)
        ruta_abs = str(carpeta.resolve()).lower()
        hash_ruta = hashlib.sha256(ruta_abs.encode("utf-8")).hexdigest()[:12]
        for m in (modulo_norm, "gemini", "deepseek", "modo_ia", "imagenes"):
            if not m:
                continue
            r_leg = self._dir_checkpoints / f"{m}_{nom_seguro}_{hash_ruta}.json"
            if r_leg.is_file():
                try:
                    r_leg.unlink(missing_ok=True)
                except OSError:
                    pass
        return True
