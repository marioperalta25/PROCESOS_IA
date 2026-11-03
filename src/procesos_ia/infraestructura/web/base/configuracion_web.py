"""Configuración y gestión de rutas y parámetros para inferencia web."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import stat
import time
from typing import Any


@dataclass(frozen=True, slots=True)
class ConfiguracionVentanaWeb:
    """Parámetros geométricos para ventana flotante sin robo de foco."""

    x: int = 1100
    y: int = 0
    ancho: int = 150
    alto: int = 450
    siempre_al_frente: bool = True
    no_activar_foco: bool = True


@dataclass(frozen=True, slots=True)
class ConfiguracionWeb:
    """Configuración integral del motor de automatización web con Nodriver."""

    directorio_base: Path = field(
        default_factory=lambda: Path(
            os.getenv(
                "PROCESOS_IA_WEB_DIR",
                str(Path.home() / ".procesos_ia" / "navegador_web"),
            )
        )
    )
    url_gemini: str = "https://gemini.google.com/app"
    url_deepseek: str = "https://chat.deepseek.com/"
    ventana: ConfiguracionVentanaWeb = field(
        default_factory=ConfiguracionVentanaWeb
    )
    max_consultas_por_chat: int = 2
    tiempo_espera_respuesta_segundos: int = 45
    tiempo_estabilidad_segundos: float = 1.0
    carpeta_imagenes: Path | None = None
    modo_procesamiento: str = "lote"
    generar_auditoria_md: bool = True

    @property
    def directorio_perfil(self) -> Path:
        """Ruta al perfil persistente de usuario para Chrome/Chromium."""
        return self.directorio_base / "perfil_usuario"

    @property
    def directorio_imagenes_temp(self) -> Path:
        """Ruta a imágenes temporales usadas durante el flujo multimodal."""
        return self.directorio_base / "temp_imagenes"

    def asegurar_directorios(self) -> None:
        """Crea las carpetas requeridas si no existen en el sistema."""
        self.directorio_base.mkdir(parents=True, exist_ok=True)
        self.directorio_perfil.mkdir(parents=True, exist_ok=True)
        self.directorio_imagenes_temp.mkdir(parents=True, exist_ok=True)

    def limpiar_bloqueos_perfil(self) -> bool:
        """Elimina archivos de bloqueo Singleton y puertos de depuracion del perfil."""
        nombres_bloqueo = (
            "SingletonLock",
            "SingletonCookie",
            "SingletonSocket",
            "DevToolsActivePort",
        )
        eliminado = False
        for nombre in nombres_bloqueo:
            archivo = self.directorio_perfil / nombre
            if archivo.exists() or archivo.is_symlink():
                try:
                    if archivo.is_dir():
                        shutil.rmtree(archivo, ignore_errors=True)
                    else:
                        archivo.unlink(missing_ok=True)
                    eliminado = True
                except OSError:
                    pass
        return eliminado

    def purgar_perfil_usuario(self, max_reintentos: int = 5) -> bool:
        """Elimina completamente el directorio del perfil asegurando permisos de escritura."""
        if not self.directorio_perfil.exists():
            self.directorio_perfil.mkdir(parents=True, exist_ok=True)
            return True

        def _desbloquear_y_borrar(func: Any, path: str, _exc: Any) -> None:
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except OSError:
                pass

        for _ in range(max_reintentos):
            try:
                shutil.rmtree(self.directorio_perfil, onerror=_desbloquear_y_borrar)
            except OSError:
                pass

            if not self.directorio_perfil.exists():
                break
            time.sleep(0.2)

        self.directorio_perfil.mkdir(parents=True, exist_ok=True)
        return True

    def limpiar_imagenes_temporales(self) -> int:
        """Elimina archivos temporales residuales en la carpeta de imágenes."""
        eliminados = 0
        if not self.directorio_imagenes_temp.exists():
            return eliminados
        for elemento in self.directorio_imagenes_temp.iterdir():
            try:
                if elemento.is_file():
                    elemento.unlink(missing_ok=True)
                    eliminados += 1
            except OSError:
                continue
        return eliminados
