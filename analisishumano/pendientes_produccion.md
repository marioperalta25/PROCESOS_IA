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

## Avance adicional - Deteccion de CAPTCHA y reinicio con perfil limpio en IA General - 2026-11-17
- Se centralizo en `gestor_resiliencia_web.py` (`es_texto_captcha_google`, `detectar_captcha_pestana`, `recuperar_si_captcha_google`) la deteccion de `/sorry/`, `#captcha-form`, `.g-recaptcha` y mensajes de trafico inusual.
- Al detectarse CAPTCHA en cualquier flujo de IA General (`ProcesadorModoIA`, `ProcesadorImagenesChat` y `ServicioIAGeneral.procesar_imagen_lens` para URL, CSV/Excel y carpetas Lens), el sistema detiene el intento actual, cierra el navegador, purga y vuelve a crear limpia la carpeta `perfil_ia_general`, espera 2.0s y reinicia el proceso hasta 3 intentos antes de abortar por bloqueo persistente.
- Validado con `test_gestor_resiliencia_web`, `test_correccion_empaquetado`, `test_ia_general` y `test_procesador_imagenes_motores` (57 pruebas OK).

## Avance adicional - Validacion de respuestas texto/pipe y reintento de lotes en Gemini y DeepSeek - 2026-11-17
- `servicio_procesamiento_web.py`: Se conecto `resp_txt` a `mapear_respuestas_lote(resp_txt or "", parsed, ...)` para aprovechar el respaldo `[FILA N]` / texto cuando Gemini o DeepSeek no devuelven JSON, y se agrego reintento de hasta 2 veces rotando chat (sin purgar `perfil_motores_web`) cuando un lote llega vacio o incompleto.
- `mapeo_respuestas_tabulares.py`: Se agrego `_expandir_texto_a_dict()` para separar en `evaluacion_col_1`, `evaluacion_col_2`, etc. cuando una respuesta en texto plano trae columnas separadas por `|`, conservando `evaluacion_ia`.
- `gestor_resiliencia_web.py`: Se ampliaron `PATRONES_CORTESIA_CONVERSACIONAL` para filtrar encabezados cortos (`Resultados:`, `Claro`, `Aquí está`) y evitar desfases posicionales.
- Validado con 76 pruebas unitarias en 8 modulos (OK).

## Avance adicional - Separacion Web/Local en creador y refinador de prompts - 2026-11-17
- `composicion_prompts.py` y `dialogo_prompt.py`: Se agrego selector de destino (`IA Web` vs `IA Local`) con paneles independientes: en `IA Web` se elige 1 columna o varias columnas (2+) y se inyecta de forma determinista el bloque JSON `{"resultados": [{"id": 1, ...}]}` mediante `aplicar_formato_salida_web()`; en `IA Local` se mantiene `EditorResultados`.
- `dominio/prompts.py`, `recursos/configuracion/evaluaciones.toml` y `refinador_ollama.py`: Se agrego `modo_destino` y `columnas_salida_objetivo` en `PeticionRefinamiento`, junto con `instruccion_refinamiento_web` y adaptacion automatica de la salida refinada para Web.
- Validado con `test_ia_general`, `test_modo_ia_conversacional`, `test_gestor_resiliencia_web` y `test_correccion_empaquetado` (63 pruebas OK).

## Avance adicional - Cancelacion inmediata sin congelacion en IA General, DeepSeek y Gemini - 2026-11-17
- Se identifico la causa del bloqueo en `"Cancelando..."`: `HiloIAGeneral.cancelar()` y `HiloProcesamientoWeb.cancelar()` cerraban el navegador sin cancelar la tarea `asyncio` activa (`loop.call_soon_threadsafe(tarea.cancel)`), dejando `await` de `nodriver` colgados; ademas `vista_ia_general._restablecer_botones_cancelacion` abortaba en un unico `singleShot(1500)` si `isRunning()` aun era `True`.
- `hilo_ia_general.py` y `hilo_procesamiento_web.py`: Ahora cancelan la tarea `asyncio` activa de inmediato y manejan `asyncio.CancelledError`.
- `procesador_modo_ia.py` y `servicio_procesamiento_web.py`: Capturan `asyncio.CancelledError` cuando hay cancelacion para garantizar el guardado del CSV parcial en `trabajo.finalizar("cancelados", ...)`.
- `vista_ia_general.py`, `vista_deepseek.py` y `vista_gemini.py`: Ejecutan `cancelar()` en hilo secundario, conectan `finished` al restablecimiento forzado y aseguran liberacion de botones por temporizador de respaldo.
- Validado con 72 pruebas unitarias en 6 modulos (OK).

## Avance adicional - Deteccion inmediata de JSON en una linea y progreso oculto en Modo IA - 2026-11-17
- Se encontro en el HTML real de Modo IA que Google incluye elementos ocultos `div.Hz4U2[role='progressbar']` dentro de los botones de copiar (`button.bKxaof`) y compartir (`button.eGAasd`), lo que hacia que `isProgress` siempre fuera `true` y `completo` siempre `false`.
- Ademas, cuando la IA respondia el JSON de 5 filas en una sola linea (`<code>...</code>` o `<span data-subtree="aimfl">...</span>`), `num_lineas` valia `1 < filas_esperadas` y bloqueaba la salida hasta agotar el timeout.
- `manipulador_dom_modo_ia.py`: Se excluyeron los `progressbar` ocultos o dentro de botones de acciones (`!el.closest("button, .RkJvxe, .OUQe0e, .zkL70c") && (el.offsetWidth > 0 || el.offsetHeight > 0)`) y se habilito retorno inmediato cuando el texto es JSON valido (`"resultados"` o `{...}`).
- Validado con `test_correccion_empaquetado` (25 pruebas OK, incluyendo `test_esperar_respuesta_modo_ia_acepta_json_una_linea_para_lote_multiple`).

## Avance adicional - Proteccion contra sobrescritura de columnas originales en CSV Web - 2026-11-17
- `mapeo_respuestas_tabulares.py`: `mapear_respuestas_lote()` ahora evita sobrescribir cualquier columna existente en la fila de entrada (ej. `categoria`, `owner`, `negocio`) y agrega automaticamente el sufijo `_ia` (`categoria_ia`, etc.) al final para Modo IA, Modo IA URLs, Gemini y DeepSeek, manteniendo intacto el llenado de columnas vacias durante la reanudacion.
- Validado con `test_modo_ia_conversacional`, `test_mapeo_progreso_tabular`, `test_correccion_empaquetado`, `test_integracion_salidas` y `test_reanudacion_consumidores` (57 pruebas OK).

## Avance adicional - Correccion de columnas de entrada vacias al evitar sobrescritura - 2026-11-18
- Se detecto en `modo_ia_FINAL_PROD_instagram_nuevos17112026.csv` que cuando una columna original del archivo (ej. `categoria`) venia vacia (`""`) en algunas filas, `TrabajoTabular` ya incluia `_estado_ia = PENDIENTE` en todas las filas y esas celdas vacias seguian escribiendose en `categoria` en vez de `categoria_ia`.
- `mapeo_respuestas_tabulares.py`: Ahora identifica como columnas originales de entrada todas las claves que aparecen antes de `_id_registro` / `_estado_ia`, enviando siempre sus resultados a `<col>_ia` incluso si la celda original venia vacia, mientras que las columnas generadas por la IA (posteriores a `_id_registro`) se actualizan normalmente en reanudaciones.
- Validado con 57 pruebas unitarias OK.

## Avance adicional - Preservacion de telefonos originales y fechas de Excel - 2026-11-18
- `guardador_extracciones.py`: `guardar_filas_enriquecidas_csv()` ahora solo aplica `desglosar_filas_por_telefono()` sobre columnas de telefono generadas por la IA (posteriores a `_id_registro` / `_estado_ia`), dejando intactas las columnas originales de entrada (como `telefono`).
- `lector_xlsx.py`: Agregado `_celda_a_texto()` para evitar sufijo ` 00:00:00` en fechas puras leidas desde Excel.
- Validado con `test_modo_ia_conversacional`, `test_correccion_empaquetado`, `test_reanudacion_consumidores` y `test_integracion_salidas` (51 pruebas OK).
