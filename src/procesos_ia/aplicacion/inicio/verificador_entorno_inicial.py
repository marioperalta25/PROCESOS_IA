"""Verificador de primer arranque y dependencias silenciosas para PROCESOS_IA."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

MODULOS_PYTHON_REQUERIDOS = (
    "PySide6",
    "nodriver",
    "psutil",
    "openpyxl",
)

RUTAS_CHROME_WINDOWS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
)


def obtener_ruta_testigo_inicial() -> Path:
    """Devuelve la ruta persistente del archivo testigo de primer arranque en AppData."""
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "PROCESOS_IA"
    base.mkdir(parents=True, exist_ok=True)
    return base / ".inicializacion_completada.json"


def es_primer_arranque() -> bool:
    """Determina si la aplicacion se esta ejecutando por primera vez en este equipo."""
    testigo = obtener_ruta_testigo_inicial()
    return not testigo.is_file()


def marcar_primer_arranque_completado(info_extra: dict[str, Any] | None = None) -> None:
    """Crea el archivo testigo para no repetir las comprobaciones en arranques posteriores."""
    testigo = obtener_ruta_testigo_inicial()
    contenido: dict[str, Any] = {
        "fecha_inicializacion": datetime.now(timezone.utc).isoformat(),
        "version_python": sys.version,
        "empaquetado": getattr(sys, "frozen", False),
    }
    if info_extra:
        contenido.update(info_extra)
    try:
        testigo.write_text(json.dumps(contenido, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def localizar_chrome_en_sistema() -> Path | None:
    """Comprueba si Google Chrome o un ejecutable compatible esta instalado."""
    hallado = shutil.which("chrome") or shutil.which("google-chrome")
    if hallado:
        return Path(hallado)
    if sys.platform == "win32":
        for ruta in RUTAS_CHROME_WINDOWS:
            p = Path(ruta)
            if p.is_file():
                return p
    return None


def localizar_ollama_en_sistema() -> Path | None:
    """Comprueba si Ollama esta instalado en las rutas habituales de Windows o PATH."""
    hallado = shutil.which("ollama")
    if hallado:
        return Path(hallado)
    if sys.platform == "win32":
        ruta_appdata = Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"))
        if ruta_appdata.is_file():
            return ruta_appdata
        ruta_prog = Path(r"C:\Program Files\Ollama\ollama.exe")
        if ruta_prog.is_file():
            return ruta_prog
    return None


def instalar_libreria_silenciosa(nombre_libreria: str, timeout_segundos: int = 120) -> bool:
    """Instala silenciosamente en segundo plano una libreria de Python sin abrir consolas."""
    if getattr(sys, "frozen", False):
        return False
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        comando = [sys.executable, "-m", "pip", "install", nombre_libreria]
        res = subprocess.run(
            comando,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=flags,
            timeout=timeout_segundos,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def verificar_entorno_primer_arranque() -> tuple[bool, list[str]]:
    """Ejecuta la verificacion de dependencias solo si es el primer arranque.

    Retorna:
        tuple[bool, list[str]]: (exito_total, lista_advertencias_o_fallos)
    """
    if not es_primer_arranque():
        return True, []

    advertencias: list[str] = []
    es_empaquetado = getattr(sys, "frozen", False)

    # 1. Comprobacion de librerias de Python (solo cuando se ejecuta desde codigo fuente)
    if not es_empaquetado:
        for lib in MODULOS_PYTHON_REQUERIDOS:
            try:
                spec = importlib.util.find_spec(lib)
            except Exception:
                spec = None

            if spec is None:
                instalado = instalar_libreria_silenciosa(lib)
                if not instalado:
                    advertencias.append(
                        f"No se pudo instalar automáticamente la librería '{lib}'. "
                        f"Por favor ejecute manualmente: pip install {lib}"
                    )

    # 2. Comprobacion de dependencias externas del sistema
    chrome = localizar_chrome_en_sistema()
    if chrome is None:
        advertencias.append(
            "No se detectó Google Chrome en el equipo. "
            "Es necesario para las funciones web de Google Lens, Gemini y DeepSeek. "
            "Puede descargarlo gratuitamente desde https://www.google.com/chrome"
        )

    ollama = localizar_ollama_en_sistema()
    if ollama is None:
        advertencias.append(
            "No se detectó Ollama instalado en el equipo. "
            "Si planea utilizar modelos de IA local, descárguelo desde https://ollama.com"
        )

    # 3. Registrar el primer arranque para que no vuelva a ejecutarse
    info = {
        "chrome_detectado": chrome is not None,
        "ollama_detectado": ollama is not None,
        "advertencias": advertencias,
    }
    marcar_primer_arranque_completado(info)

    exito = len(advertencias) == 0
    return exito, advertencias
