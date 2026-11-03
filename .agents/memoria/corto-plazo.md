# Estado breve

Actualización: 2 de noviembre de 2026. Telemetría de tokens/caracteres en vivo, control de desbordamiento de plantillas y etiquetas guía responsivas para IA General.

## Encargo y resultado

Implementadas las siguientes mejoras críticas bajo supervisión y requerimientos del usuario:
1. Telemetría y aseguramiento de tokens/caracteres en tiempo real para plantillas de Modo IA:
   - Nuevo componente `medidor_tokens.py` con estimación multilingüe (~3.8 caracteres por token) y límite de 8,000 caracteres de Google Modo IA.
   - Etiqueta interactiva `EtiquetaContadorTokens` en vivo (`[OK]`, `[ALERTA]`, `[ERROR]`) con semáforo de estados (verde seguro, naranja próximo, rojo exceso).
   - Bloqueo preventivo en `_ejecutar_accion()` y advertencia en `obtener_parametros()` si el texto excede los 8,000 caracteres, garantizando que el prompt jamás se corte silenciosamente en el navegador.
2. Labels descriptivos y responsivos para orientar al usuario en todas las secciones de IA General:
   - Nueva barra de acciones modular `BarraAccionesIAGeneral` con guía descriptiva de botones (`Iniciar`, `Detener`, `Destino...`, `Abrir Salida`) y tooltips completos.
   - Guía responsiva de operación en `vista_ia_general.py` (`lbl_guia_flujo`) explicando las diferencias entre Modo IA y Google Lens.
   - Guías paso a paso numeradas en `panel_modo_chat.py` (1. Archivo, 2. Columnas con |, 3. Instrucciones, 4. Lotes) y `panel_archivo_general.py`.
   - Adaptación dinámica de textos según el modo de pantalla (`ModoPantalla.COMPACTO`, `ESTANDAR`, `AMPLIO`).

## Implementación

- `medidor_tokens.py`: lógica de cálculo de tokens, umbrales de seguridad y widget `EtiquetaContadorTokens` responsivo.
- `barra_acciones_ia_general.py`: desacoplamiento de botones de ejecución y su barra de ayuda responsiva.
- `panel_modo_chat.py`: integración de etiquetas numeradas, contador en tiempo real conectado al editor expandible y validación preventiva.
- `vista_ia_general.py`: integración de `BarraAccionesIAGeneral`, guía de flujo y control de desbordamiento antes de lanzar el hilo de ejecución.
- `panel_archivo_general.py`: label informativo responsivo para selección de archivo y columnas.
- `editor_texto_expandible.py`: alias de compatibilidad `textChanged = texto_cambiado`.

## Verificación

- Suite completa de 313 pruebas unitarias aprobada exitosamente: `Ran 313 tests in 82.669s, OK`.
- Límite máximo de 300 líneas físicas verificado y cumplido estrictamente en todos los archivos.
- Cero emojis en código, interfaz, logs y respuestas.
