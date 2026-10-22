"""Comprueba el esquema local sin red ni dependencias externas (Python 3.11+)."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import tomllib
from urllib.parse import unquote, urlsplit


EXCLUIDAS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist",
    "preparacion-orden", "datos_locales", "registros", "modelos_descargados",
}
EXTENSIONES_CODIGO = {
    ".py", ".pyi", ".js", ".ts", ".jsx", ".tsx", ".qml", ".qss", ".css",
    ".html", ".sql", ".ps1", ".bat", ".sh",
}
METADATOS = re.compile(r"\A---\n(.*?)\n---\n(.+)", re.S)
ENLACES = re.compile(r"\[[^\]\n]+\]\(([^)\n]+)\)")


def sin_bloques(contenido: str) -> str:
    """Evita interpretar ejemplos de código como enlaces documentales."""
    return re.sub(r"(?ms)^```[^\n]*\n.*?^```\s*$", "", contenido)


def anclas(contenido: str) -> set[str]:
    """Reconoce las anclas simples utilizadas por estos documentos."""
    resultado = set()
    for titulo in re.findall(r"(?m)^#{1,6}\s+(.+)$", sin_bloques(contenido)):
        titulo = re.sub(r"[^\w\s-]", "", titulo.lower())
        resultado.add(titulo.replace(" ", "-"))
    return resultado


def revisar_enlaces(ruta: Path, contenido: str) -> list[str]:
    fallos = []
    for referencia in ENLACES.findall(sin_bloques(contenido)):
        destino = urlsplit(referencia.strip("<>"))
        if destino.scheme or destino.netloc:
            continue
        archivo = ruta.parent / unquote(destino.path) if destino.path else ruta
        if not archivo.is_file():
            fallos.append(f"{ruta.name}: enlace local inexistente: {referencia}")
        elif destino.fragment and archivo.suffix == ".md":
            if unquote(destino.fragment) not in anclas(archivo.read_text(encoding="utf-8")):
                fallos.append(f"{ruta.name}: ancla no encontrada: {referencia}")
    return fallos


def revisar_habilidad(ruta: Path, contenido: str) -> list[str]:
    """Valida el subconjunto de YAML simple usado aquí; no es un parser general."""
    fallos = []
    coincidencia = METADATOS.fullmatch(contenido)
    if not coincidencia:
        return [f"{ruta}: faltan metadatos o cuerpo de la habilidad"]
    campos = {}
    for linea in coincidencia[1].splitlines():
        clave, separador, valor = linea.partition(": ")
        if not separador or clave not in {"name", "description"} or clave in campos:
            fallos.append(f"{ruta}: metadatos fuera del formato simple: {linea}")
            continue
        if not valor or re.search(r":\s|\s#|[\[\]{}]", valor):
            fallos.append(f"{ruta}: valor de metadatos no admitido")
        elif valor[0] in "-?:,>&*!|%'\"@`":
            fallos.append(f"{ruta}: usar texto simple en los metadatos")
        campos[clave] = valor
    nombre = campos.get("name", "")
    descripcion = campos.get("description", "")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", nombre):
        fallos.append(f"{ruta}: nombre de habilidad inválido")
    if nombre != ruta.parent.name or not 1 <= len(nombre) <= 64:
        fallos.append(f"{ruta}: nombre distinto de la carpeta o longitud inválida")
    if not 1 <= len(descripcion) <= 1024:
        fallos.append(f"{ruta}: descripción ausente o demasiado larga")
    if "../../reglas/AGENTS.md" not in coincidencia[2]:
        fallos.append(f"{ruta}: falta referencia a las reglas comunes")
    return fallos


def medir_objetivos(raiz: Path, parametros: dict) -> list[str]:
    objetivos = parametros["objetivos_editoriales"]
    memoria = parametros["memoria"]
    metas = {
        parametros["esquema"]["entrada"]: objetivos["palabras_entrada"],
        memoria["corto_plazo"]: objetivos["palabras_memoria_corta"],
        memoria["largo_plazo"]: objetivos["palabras_indice_duradero"],
    }
    habilidades = raiz / parametros["esquema"]["habilidades"]
    for ruta in habilidades.glob("*/SKILL.md"):
        metas[str(ruta.relative_to(raiz))] = objetivos["palabras_por_habilidad"]
    avisos = []
    for nombre, limite in metas.items():
        ruta = raiz / nombre
        if ruta.is_file():
            cantidad = len(ruta.read_text(encoding="utf-8").split())
            print(f"{nombre}: {cantidad} palabras; objetivo editorial {limite}.")
            if cantidad > limite:
                avisos.append(f"Revisar crecimiento de contexto: {nombre}")
    return avisos


def verificar(raiz: Path) -> int:
    fallos = []
    try:
        parametros = tomllib.loads((raiz / ".agents" / "configuracion" / "agentes.toml").read_text(encoding="utf-8"))
        limite_codigo = parametros["limites"]["lineas_codigo"]
        limite_habilidad = parametros["limites"]["lineas_habilidad"]
        if limite_codigo != 300:
            raise ValueError("La regla del proyecto es 300 líneas de código")
        for clave in ("corto_plazo", "largo_plazo", "registro_decisiones"):
            if not (raiz / parametros["memoria"][clave]).is_file():
                raise ValueError(f"Falta archivo de memoria: {clave}")
        if not (raiz / parametros["esquema"]["entrada"]).is_file():
            raise ValueError("Falta archivo de entrada")
    except (OSError, ValueError, KeyError) as error:
        print(f"ERROR: parámetros incompletos o inválidos: {error}")
        return 1

    archivos = [
        ruta for ruta in raiz.rglob("*")
        if ruta.is_file() and not EXCLUIDAS.intersection(ruta.relative_to(raiz).parts)
        and (ruta.suffix in EXTENSIONES_CODIGO | {".md", ".toml"})
    ]
    habilidades = []
    for ruta in sorted(archivos):
        try:
            contenido = ruta.read_text(encoding="utf-8")
            if ruta.suffix == ".toml":
                tomllib.loads(contenido)
            if ruta.suffix == ".md":
                fallos.extend(revisar_enlaces(ruta, contenido))
            if ruta.suffix in EXTENSIONES_CODIGO and len(contenido.splitlines()) > limite_codigo:
                fallos.append(f"{ruta}: supera el límite de código")
            if not contenido.endswith("\n"):
                fallos.append(f"{ruta}: falta salto final")
            if re.search("[\U0001F000-\U0001FAFF\u2600-\u27BF]", contenido):
                fallos.append(f"{ruta}: posible emoji")
            if ruta.name == "SKILL.md":
                habilidades.append(ruta)
                fallos.extend(revisar_habilidad(ruta, contenido))
                if len(contenido.splitlines()) > limite_habilidad:
                    fallos.append(f"{ruta}: supera el límite editorial de habilidad")
        except (OSError, UnicodeError, ValueError) as error:
            fallos.append(f"{ruta}: no se pudo validar: {error}")

    directorio = raiz / parametros["esquema"]["habilidades"]
    carpetas = list(directorio.iterdir()) if directorio.is_dir() else []
    if not carpetas or not habilidades:
        fallos.append("No se encontraron habilidades en la ruta configurada")
    for carpeta in carpetas:
        if carpeta.is_dir() and not (carpeta / "SKILL.md").is_file():
            fallos.append(f"{carpeta}: falta SKILL.md")
    avisos = medir_objetivos(raiz, parametros)
    for aviso in avisos:
        print(f"AVISO: {aviso}")
    for fallo in fallos:
        print(f"ERROR: {fallo}")
    print(f"Archivos revisados: {len(archivos)}; habilidades: {len(habilidades)}.")
    print("Resultado estructural: " + ("CON FALLOS" if fallos else "CORRECTO"))
    print("No mide tokens ni cumplimiento de instrucciones por un LLM.")
    return int(bool(fallos))


def principal() -> int:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[2])
    opciones = argumentos.parse_args()
    return verificar(opciones.raiz.resolve())


if __name__ == "__main__":
    sys.exit(principal())
