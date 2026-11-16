# -*- mode: python ; coding: utf-8 -*-
"""Especificacion de compilacion optimizada de PyInstaller para PROCESOS_IA."""

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

bloque_cifrado = None

# Recolectar datos estrictamente necesarios de recursos
datos_recursos = [
    ('recursos', 'recursos'),
]

# Modulos y componentes pesados de Qt no utilizados
modulos_excluidos = [
    'unittest',
    'test',
    'pruebas',
    'tkinter',
    'matplotlib',
    'IPython',
    'notebook',
    'scipy',
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuickWidgets',
    'PySide6.QtPdf',
    'PySide6.QtPdfWidgets',
    'PySide6.QtVirtualKeyboard',
    'PySide6.QtDesigner',
    'PySide6.QtHelp',
    'PySide6.QtSpatialAudio',
    'PySide6.QtTest',
]

# Submodulos requeridos para la interaccion CDP con el navegador
submodulos_nodriver = collect_submodules('nodriver')

importaciones_ocultas = [
    'procesos_ia',
    'tomllib',
    'openpyxl',
    'psutil',
    'nodriver',
    'win32api',
    'win32gui',
    'win32process',
    'win32con',
    'pywintypes',
] + submodulos_nodriver

analisis = Analysis(
    ['src/procesos_ia/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=datos_recursos,
    hiddenimports=importaciones_ocultas,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=modulos_excluidos,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=bloque_cifrado,
    noarchive=False,
)

# Filtro de binarios no utilizados en la aplicacion de escritorio
binarios_ignorar = ('Qt6Qml', 'Qt6Quick', 'Qt6Pdf', 'Qt6VirtualKeyboard', 'opengl32sw')
binarios_optimizados = [
    b for b in analisis.binaries
    if not any(nom in b[0] for nom in binarios_ignorar)
]

# Excluir catalogo de traducciones innecesarias de Qt
datas_optimizados = [
    d for d in analisis.datas
    if not (d[0].endswith('.qm') and 'translations' in d[0])
]

pyz = PYZ(analisis.pure, analisis.zipped_data, cipher=bloque_cifrado)

ejecutable = EXE(
    pyz,
    analisis.scripts,
    [],
    exclude_binaries=True,
    name='PROCESOS_IA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='recursos/imagenes/icono-aplicacion.ico',
)

coleccion = COLLECT(
    ejecutable,
    binarios_optimizados,
    analisis.zipfiles,
    datas_optimizados,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PROCESOS_IA',
)
