# Seguimiento de hallazgos y mejoras para producción

Archivo de registro acumulativo (solo anexar avances y verificaciones sin borrar el historial previo).

---

## Registro inicial - 2026-11-16

### Contexto previo resuelto en esta sesión
- **Parte 1 (`csv_lens` en IA General)**: trazabilidad en bitácora (`ConsolaIAGeneral`) ante abortos de validación, cancelación/falta de pendientes en preparación tabular, exportación directa sin abrir navegador, filas vacías y errores al abrir pestaña en [vista_ia_general.py](file:///c:/Users/mgutierrez/Desktop/Librerias%20Python/PROCESOS_IA/src/procesos_ia/interfaz/ia_web/vistas/vista_ia_general.py), [procesador_archivo_urls.py](file:///c:/Users/mgutierrez/Desktop/Librerias%20Python/PROCESOS_IA/src/procesos_ia/aplicacion/ia_web/visual_1a1/procesador_archivo_urls.py) y [servicio_ia_general.py](file:///c:/Users/mgutierrez/Desktop/Librerias%20Python/PROCESOS_IA/src/procesos_ia/aplicacion/ia_web/visual_1a1/servicio_ia_general.py).
- **Parte 2 (Control de ventana Win32 y Nodriver)**: restauración sin robo de foco (`SW_SHOWNOACTIVATE`) para ventanas maximizadas o minimizadas, patrones de título compartidos desde `navegador.toml`, reaplicación de geometría si cambia la configuración con navegador abierto y ampliación de `tiempo_posicion_segundos` a `8.0` en [controlador_ventana.py](file:///c:/Users/mgutierrez/Desktop/Librerias%20Python/PROCESOS_IA/src/procesos_ia/infraestructura/web/base/controlador_ventana.py), [gestor_sesion_nodriver.py](file:///c:/Users/mgutierrez/Desktop/Librerias%20Python/PROCESOS_IA/src/procesos_ia/infraestructura/web/base/gestor_sesion_nodriver.py) y [navegador.toml](file:///c:/Users/mgutierrez/Desktop/Librerias%20Python/PROCESOS_IA/recursos/configuracion/navegador.toml).

---

## Puntos pendientes por resolver y verificar

### Punto 1: `asyncio.get_event_loop()` en módulos web pendientes
- **Estado**: `[PENDIENTE]`
- **Descripción**: En Python 3.14 dentro de hilos `QThread`, varios módulos web aún utilizan `asyncio.get_event_loop()` en lugar de `asyncio.get_running_loop()`.
- **Módulos identificados**:
  - `src/procesos_ia/aplicacion/ia_web/comun/gestor_resiliencia_web.py`
  - `src/procesos_ia/aplicacion/ia_web/conversacional/procesador_imagenes_chat.py`
  - `src/procesos_ia/aplicacion/ia_web/conversacional/procesador_modo_ia.py`
  - `src/procesos_ia/aplicacion/ia_web/motores/procesador_imagenes_motores.py`
  - `src/procesos_ia/aplicacion/ia_web/motores/servicio_procesamiento_web.py`
  - `src/procesos_ia/aplicacion/ia_web/visual_1a1/procesador_carpeta_imagenes.py`
  - `src/procesos_ia/infraestructura/web/base/servicio_inferencia_web.py`
  - `src/procesos_ia/infraestructura/web/conversacional/manipulador_dom_modo_ia.py`
  - `src/procesos_ia/infraestructura/web/motores/manipulador_dom_deepseek.py`
  - `src/procesos_ia/infraestructura/web/motores/manipulador_dom_gemini.py`
  - `src/procesos_ia/infraestructura/web/visual_1a1/manipulador_dom_lens.py`
- **Plan de verificación**: Migrar a `asyncio.get_running_loop()` (y validar si `servicio_inferencia_web.py` requiere manejo específico de bucle) y ejecutar las pruebas unitarias de cada segmento.

### Punto 2: Persistencia de geometría y ancho mínimo
- **Estado**: `[PENDIENTE]`
- **Descripción**: `ConfiguracionVentanaWeb` se actualiza únicamente en memoria desde `PanelOpcionesAvanzadasWeb` y se pierde al cerrar la aplicación. Además, su valor predeterminado `ancho = 150` en `src/procesos_ia/infraestructura/web/base/configuracion_web.py` es menor que el mínimo del `QSpinBox` (`200`) y que el ancho mínimo impuesto por Chrome en Windows.
- **Plan de verificación**: Definir persistencia local de preferencias de ventana, alinear el valor predeterminado con el rango válido del control y comprobar en pruebas que la configuración persiste entre sesiones.

### Punto 3: Foco inicial al lanzar Chrome
- **Estado**: `[PENDIENTE]`
- **Descripción**: `SWP_NOACTIVATE` evita robar el foco al reposicionar la ventana con `SetWindowPos`, pero no impide que Windows active Chrome en el instante en que `uc.start` o `new_tab=True` crea la ventana antes de ejecutar `SetWindowPos`.
- **Plan de verificación**: Evaluar estrategia controlada para preservar o devolver el foco de la ventana principal al iniciar o abrir pestaña sin interferir con la interacción manual del usuario, y validarlo con pruebas unitarias y ejecución real.

### Punto 4: Visibilidad de `ultimo_aviso_ventana`
- **Estado**: `[PENDIENTE]`
- **Descripción**: `gestor_sesion_nodriver.py` ya almacena `ultimo_aviso_ventana` cuando falla el posicionamiento Win32, pero `ServicioIAGeneral` y `ServicioProcesamientoWeb` todavía no lo reenvían a `callback_log` para que aparezca en `ConsolaIAGeneral` en la versión empaquetada sin consola (`console=False`).
- **Plan de verificación**: Propagar `ultimo_aviso_ventana` hacia `callback_log` tras abrir navegador o pestaña en ambos servicios y comprobar en pruebas que el aviso aparece en la bitácora.

### Punto 5: Empaquetado y validación en ejecutable real
- **Estado**: `[PENDIENTE]`
- **Descripción**: `empaquetar.bat` apunta a `empaquetado\compilar.ps1`, carpeta que no existe actualmente en el repositorio. Falta compilar el nuevo `.exe` y validarlo con Chrome real en entorno de producción.
- **Plan de verificación**: Revisar o reconstruir el flujo de compilación con `PROCESOS_IA.spec`, ejecutar la comprobación de distribución (`--comprobar-distribucion`) y validar manualmente los flujos con Chrome real.

---

## Avance Punto 1 - `asyncio.get_event_loop()` -> `asyncio.get_running_loop()` - 2026-11-16
- **Estado**: `[RESUELTO]`
- **Archivos actualizados**:
  - `src/procesos_ia/aplicacion/ia_web/comun/gestor_resiliencia_web.py`
  - `src/procesos_ia/aplicacion/ia_web/conversacional/procesador_imagenes_chat.py`
  - `src/procesos_ia/aplicacion/ia_web/conversacional/procesador_modo_ia.py`
  - `src/procesos_ia/aplicacion/ia_web/motores/procesador_imagenes_motores.py`
  - `src/procesos_ia/aplicacion/ia_web/motores/servicio_procesamiento_web.py`
  - `src/procesos_ia/aplicacion/ia_web/visual_1a1/procesador_carpeta_imagenes.py`
  - `src/procesos_ia/infraestructura/web/base/servicio_inferencia_web.py`
  - `src/procesos_ia/infraestructura/web/conversacional/manipulador_dom_modo_ia.py`
  - `src/procesos_ia/infraestructura/web/motores/manipulador_dom_deepseek.py`
  - `src/procesos_ia/infraestructura/web/motores/manipulador_dom_gemini.py`
  - `src/procesos_ia/infraestructura/web/visual_1a1/manipulador_dom_lens.py`
- **Verificación ejecutada**:
  - Búsqueda en todo `src/`: `0` ocurrencias restantes de `get_event_loop`.
  - `python -B pruebas/ejecutar_reanudacion.py test_gestor_resiliencia_web test_modo_ia_imagenes test_procesador_imagenes_motores test_subservicios_ia_web test_inferencia_web test_modo_ia_conversacional test_vistas_deepseek_gemini test_lens_dom`: **71 pruebas ejecutadas, 71 aprobadas** (`OK`, con motores simulados).

---

## Avance Punto 2 - Persistencia de geometría y ancho mínimo - 2026-11-16
- **Estado**: `[RESUELTO]`
- **Cambios realizados**:
  - Creado `src/procesos_ia/interfaz/comun/preferencias_web.py` con `cargar_configuracion_web` y `guardar_configuracion_web` mediante `QSettings("PROCESOS_IA", "PROCESOS_IA")` (ancho, alto, siempre al frente, tiempo de espera y auditoría `.md`).
  - Actualizado `ConfiguracionVentanaWeb.ancho` predeterminado de `150` a `500` en `src/procesos_ia/infraestructura/web/base/configuracion_web.py` para alinearlo con `PanelOpcionesAvanzadasWeb` (`>= 200`) y el ancho mínimo de Chrome en Windows.
  - Conectada carga al iniciar y guardado al confirmar en `src/procesos_ia/interfaz/ventana_principal.py`.
- **Verificación ejecutada**:
  - `test_preferencias_web_persisten_y_ancho_predeterminado_es_valido` en `pruebas/unitarias/test_correccion_empaquetado.py`.
  - `python -B pruebas/ejecutar_reanudacion.py test_correccion_empaquetado test_inferencia_web test_vistas_deepseek_gemini test_interfaz`: **39 pruebas ejecutadas, 39 aprobadas** (`OK`).
