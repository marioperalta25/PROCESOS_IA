# Analisis y Diseno: Reprocesos y Reanudacion Basada en Metadatos de Estado

Fecha: 10 de Noviembre de 2026
Contexto: PROCESOS_IA - Reanudacion granular y controlada para procesos tabulares (IA General, DeepSeek, Gemini, Lens) y Carpetas de Imagenes.

---

## 1. Problema de la Evaluacion Ciega

Actualmente, si se evalua el progreso unicamente por la cantidad de filas escritas o si el nombre del archivo de imagen existe en el CSV previo:
- **Filas o imagenes fallidas quedan desatendidas**: Si de 200 filas escritas (o 200 fotos), 15 fallaron (por alucinacion del LLM, timeout, desconexion o error HTTP), saltar a la 201 ignora esas 15 y las da por completadas sin reintento.
- **Sin trazabilidad del motivo de fallo**: El sistema no distingue entre un registro exitoso, un error de red, una omision del modelo o uno pendiente.
- **Riesgo ante cancelacion abrupta**: El corte a mitad de lote deja datos en un estado inconsistente.

---

## 2. Modelo Universal de Metadatos de Estado (CSVs e Imagenes)

Para lograr un sistema modular, robusto y escalable sin trabajar a ciegas:

### 2.1 Columnas Estandarizadas de Metadatos
Cada registro (fila de CSV o imagen en carpeta) incorpora:
- `_estado_ia`:
  - `EXITOSO`: Respuesta recibida, parseada y validada correctamente.
  - `FALLIDO`: Hubo error de conexion, timeout, error HTTP o excepcion no recuperable.
  - `OMITIDO`: El LLM envio respuesta pero ignoro o devolvio vacio este registro del lote.
  - `PENDIENTE`: Registro aun no enviado al modelo o cancelado antes de su turno.
- `_motivo_estado`: Detalle conciso del estado (ej. `[OK] Evaluado`, `[ERROR] Timeout de respuesta`).
- `_fecha_procesamiento`: Marca temporal ISO de cuando se proceso la fila o imagen.

### 2.2 Deteccion Inteligente de Estado
Al cargar un archivo CSV o seleccionar una carpeta de imagenes:
1. **Verificacion de Metadatos Previos**:
   - Si **NO existen columnas de metadatos**: Es un archivo nuevo. Se corre desde cero asignando columnas con estado `PENDIENTE`.
   - Si **SI existen** (o se localiza un respaldo en `cancelados/` o `en_proceso/`):
     - El sistema audita y clasifica:
       - Total de elementos: `N`
       - Exitosos: `E`
       - Fallidos / Omitidos / Timeout: `F`
       - Pendientes nunca procesados: `P`
2. **Presentacion de Decision al Usuario**:
   Se presenta una ventana de dialogo nativa moderna con las opciones precisas.

---

## 3. Interfaz de Usuario y Proteccion de Botones (Dialogo Flotante Nativo)

### 3.1 Ventana Flotante Modal Nativa (`QDialog` estilizado)
En lugar de un simple alert basico, se despliega un dialogo flotante nativo estilizado acorde a la paleta del sistema:
- **Encabezado con Diagnostico Claro**:
  - `[INFO] Se detecto avance previo para este archivo / carpeta:`
  - `Total registros: N | Exitosos: E | Fallidos / Omitidos: F | Pendientes: P`
- **Botones de Accion Clara**:
  1. `[Reprocesar Pendientes y Fallidos]` (Recomendado cuando F > 0): Procesa los `F` y `P` conservando intactos los `E`.
  2. `[Solo Procesar Pendientes]` (Aparece si P > 0): Ignora los fallidos y procesa unicamente los no iniciados.
  3. `[Reiniciar Todo desde Cero]`: Limpia metadatos y corre el lote completo.
  4. `[Cancelar]`: Cierra el dialogo y no inicia el procesamiento.

### 3.2 Proteccion Antirebote (`ProtectorBotones`)
- Todos los botones del dialogo se conectan a traves de `ProtectorBotones.vincular(...)`:
  - Bloqueo inmediato tras el primer clic (`tiempo_bloqueo_ms = 600`).
  - Previene doble ejecucion accidental o spam de clics en el arranque de hilos.
  - Notificacion visual en consola/log de la accion seleccionada por el usuario.

---

## 4. Arquitectura Modular

```
src/procesos_ia/
  ├── aplicacion/ia_web/comun/
  │     └── gestor_metadatos_estado.py    <-- Nucleo puro de analisis y clasificacion (O(1))
  ├── interfaz/ia_web/comun/
  │     └── dialogo_reanudacion_estado.py <-- Dialogo modal nativo estilizado con ProtectorBotones
  └── aplicacion/.../
        ├── procesador_modo_ia.py         <-- Consumidor en IA General
        ├── servicio_procesamiento_web.py <-- Consumidor en DeepSeek y Gemini
        └── procesador_carpeta_imagenes.py<-- Consumidor en Lens y Motores Visuales
```

---

# Bitacora de Implementacion Realizada

Fecha: 10 de Noviembre de 2026 - 15:15
Estado: Fase 1 Completada con Exito

## 1. Modulos Creados y Verificados (Arquitectura Padre-Hijo)
1. **Contratos de Dominio Centralizados**:
   - Archivo: `src/procesos_ia/dominio/reanudacion.py` (80 lineas).
   - Define: `EstadoIA` (EXITOSO, FALLIDO, OMITIDO, PENDIENTE), `AccionReanudacion`, `RegistroEstado` y `ResumenReanudacion`.
2. **Nucleo Padre Troncal**:
   - Archivo: `src/procesos_ia/aplicacion/comun/gestor_reanudacion_base.py` (126 lineas).
   - Metodos: Lectura generadora O(1) de memoria, normalizacion de estados y motivos, clasificacion estadistica (N, E, F, P) y filtrado de elementos por accion.
3. **Hijo Especializado en Tabulares (CSVs)**:
   - Archivo: `src/procesos_ia/aplicacion/ia_web/comun/gestor_reanudacion_tabular.py` (118 lineas).
   - Metodos: Localizacion automatica de respaldos previos en cancelados/ o en_proceso/, preparacion de filas para reenvio recuperando fallidas y pendientes sin duplicar ni perder las exitosas.
4. **Hijo Especializado en Carpetas de Imagenes**:
   - Archivo: `src/procesos_ia/aplicacion/ia_web/comun/gestor_reanudacion_imagenes.py` (90 lineas).
   - Metodos: Auditoria de carpetas de fotos contra CSV incremental y discriminacion de errores de timeout/envio.
5. **Dialogo Nativo Flotante Modal con Proteccion Antirebote**:
   - Archivo: `src/procesos_ia/interfaz/comun/dialogo_reanudacion.py` (167 lineas).
   - Componentes: QDialog modal, panel de metricas visuales (Total, Exitosos, Fallidos/Omitidos, Pendientes), boton recomendado inteligente, botones protegidos con ProtectorBotones (cooldown de 600 ms).
6. **Bateria de Pruebas Automatizadas**:
   - Archivo: `pruebas/unitarias/test_reanudacion_jerarquica.py` (103 lineas).
   - Cobertura: Verificacion de clasificacion, filtrado por accion y preparacion de lote tabular. 3 tests aprobados (OK).
   - Suite de regresion previa: 35 tests aprobados (OK) en test_ia_general, test_integracion_salidas y test_vistas_deepseek_gemini.

## 2. Proximo Paso: Fase 2
- Conectar el Hijo Tabular en **IA General** (`procesador_modo_ia.py` y `vista_ia_general.py`) para presentar el dialogo nativo antes del arranque y enviar unicamente las filas que correspondan segun la decision del usuario.

---

# Seccion Analisis de Impacto: Conexion del Gestor Tabular en IA General

Fecha: 10 de Noviembre de 2026 - 15:16
Objetivo: Conectar GestorReanudacionTabular y DialogoReanudacionEstado en Modo IA Lotes de IA General.

## 1. Que hace la implementacion actual
- En `vista_ia_general.py` (lineas 173-181): Al seleccionar `modo_ia`, lee todas las filas del archivo y las envia sin verificar si ya existia una corrida previa o un archivo cancelado con filas evaluadas o fallidas.
- En `procesador_modo_ia.py`: Comienza siempre desde la fila 0 (`i = 0`). Asigna `evaluacion_ia` pero no agrega las columnas de estado estructurado (`_estado_ia`, `_motivo_estado`, `_fecha_procesamiento`).

## 2. Cambios a Realizar y Modulos Afectados
1. `procesador_modo_ia.py`:
   - Al mapear respuestas del lote, si una fila recibio evaluacion valida, asigna:
     `_estado_ia = "EXITOSO"` y `_motivo_estado = "[OK] Evaluado"`.
   - Si no recibio evaluacion valida (omitida por el LLM), asigna:
     `_estado_ia = "OMITIDO"` y `_motivo_estado = "[ALERTA] Omitido por LLM"`.
   - Soportar el parametro opcional `salida_retomada: SalidaProceso | None = None`. Si se recibe, reutiliza la carpeta existente sin recrear desde cero.
2. `vista_ia_general.py`:
   - En `_ejecutar_accion()`, para el flujo `modo_ia`:
     - Instanciar `GestorReanudacionTabular(self._servicio.enrutador)`.
     - Evaluar la ruta del archivo: `regs, resumen = gestor.evaluar_origen(ruta_archivo)`.
     - Si `resumen.requiere_decision`:
       - Abrir `DialogoReanudacionEstado(resumen, parent=self)`.
       - Si el usuario selecciona Cancelar -> Abortar limpiamente.
       - Si selecciona Continuar (recuperar fallidos o solo pendientes) -> Filtrar y preparar filas con `gestor.preparar_filas_para_envio(...)` y retomar la salida.
       - Si selecciona Reiniciar todo -> Procesar completo desde cero.

## 3. Garantias
- Se mantiene el limite estricto <= 300 lineas en todos los archivos.
- Cero emojis en logs y textos de la UI.
- No afecta las pruebas unitarias existentes.

---

# Cierre de Integracion: Reanudacion Inteligente en IA General

Fecha: 10 de Noviembre de 2026 - 15:28
Estado: Integracion Completa y Verificada al 100%

## Logros Obtenidos:
1. **Deteccion y Dialogo Modal Nativo en IA General**:
   - Al cargar un archivo CSV o seleccionar Modo IA en `vista_ia_general.py`, el sistema audita si existen registros procesados previamente o carpetas inconclusas en `cancelados/` o `en_proceso/`.
   - Si detecta avance, abre el dialogo modal nativo estilizado mostrando el desglose real: Total, Exitosos, Fallidos/Omitidos y Pendientes.
   - Si el usuario decide continuar recuperando fallidos o solo pendientes, `gestor_reanudacion_tabular.py` filtra el dataset preparando exactamente las filas a reenviar y retoma la carpeta de salida sin recrear desde cero.
2. **Enriquecimiento de Fila Fila con Metadatos**:
   - Cada fila procesada en `procesador_modo_ia.py` incorpora:
     - `_estado_ia` (EXITOSO si respondio el LLM, OMITIDO si fue ignorado por el LLM).
     - `_motivo_estado` ([OK] Evaluado / [ALERTA] No devuelto por LLM en este lote).
     - `_fecha_procesamiento` (marca de tiempo ISO).
3. **Control de Reglas y Calidad**:
   - 100% de los archivos modificados cumplen estrictamente la regla de <= 300 lineas fisicas.
   - Cero emojis en codigo, mensajes, logs y dialogos.
   - Suite de 45 pruebas unitarias integradas ejecutadas y aprobadas exitosamente (0 fallos, 0 errores).

---

# Analisis de Impacto: Reanudacion Inteligente en DeepSeek y Motores Web

Fecha: 10 de Noviembre de 2026 - 15:42
Objetivo: Conectar GestorReanudacionTabular, GestorReanudacionImagenes y DialogoReanudacionEstado en DeepSeek Web y Gemini Web.

## 1. Que hace la implementacion actual
- En `vista_deepseek.py` (y analogamente `vista_gemini.py`):
  - En flujo CSV tabular: Al pulsar Iniciar Procesamiento, no consulta estados previos; siempre arranca desde el lote 0.
  - En flujo de imagenes: Usa `verificar_estado_carpeta_imagenes` pero descarta fotos en timeout/error y solo tiene un cuadro basico QMessageBox.
- En `servicio_procesamiento_web.py`:
  - `_procesar_flujo_texto_lotes` no asigna columnas de metadatos (`_estado_ia`, `_motivo_estado`, `_fecha_procesamiento`).
  - `_procesar_flujo_imagenes` no asigna columnas de metadatos estandarizadas.
- En `procesador_imagenes_motores.py`:
  - Guarda en CSV pero las imagenes con fallo quedan marcadas como `ERROR_PARSE` o `ERROR_ENVIO` sin permitir al usuario reintentarlas granularmente sin borrar todo.

## 2. Cambios a Realizar y Modulos Involucrados
1. `servicio_procesamiento_web.py`:
   - Soportar el parametro opcional `salida_existente: SalidaProceso | None = None` en `procesar_csv()` y `_procesar_flujo_texto_lotes()`.
   - Enriquecer cada fila procesada con:
     - `_estado_ia` (EXITOSO si hubo extraccion/respuesta, FALLIDO si hubo fallo de envio o timeout, OMITIDO si vino vacio).
     - `_motivo_estado` ([OK] Evaluado / [ERROR] Fallo de envio / [ALERTA] Respuesta no estructurada).
     - `_fecha_procesamiento` (marca temporal ISO).
2. `vista_deepseek.py` (y `vista_gemini.py` / `vista_motores.py`):
   - Al pulsar Iniciar en flujo CSV:
     - Consultar `GestorReanudacionTabular`.
     - Si `resumen.requiere_decision`: Abrir `DialogoReanudacionEstado`.
     - Si selecciona continuar: Filtrar filas con `preparar_filas_para_envio()` y pasar `salida_existente` al hilo.
   - Al pulsar Iniciar en flujo de imagenes:
     - Consultar `GestorReanudacionImagenes`.
     - Si `resumen.requiere_decision`: Abrir `DialogoReanudacionEstado(..., es_carpeta_imagenes=True)`.
     - Si selecciona continuar: Filtrar imagenes pendientes y fallidas con `filtrar_imagenes()`.

## 3. Garantias
- Regla estricta <= 300 lineas por archivo.
- Cero emojis.
- Compatibilidad absoluta con la suite de pruebas existente.


---

# Fase 4: Reanudacion Inteligente en Google Lens y Procesamiento Local

- **Google Lens (CSV Tabular y Carpetas)**:
  - `procesador_archivo_urls.py`: Incorporacion de metadatos (`_estado_ia`, `_motivo_estado`, `_fecha_procesamiento`) y soporte para `salida_existente`.
  - `vista_ia_general.py`: Integracion con `GestorReanudacionTabular` para `csv_lens` y `GestorReanudacionImagenes` para `carpeta`.
- **Procesamiento Local**:
  - `continuacion_local.py`: Integracion con `solicitar_decision_reanudacion` manteniendo la proteccion de botones y la coherencia visual con el resto del sistema.


---

# Bitacora Final: Sistema de Reanudacion y Reprocesos Granulares

- **Fecha de culminacion**: 10 de Noviembre de 2026.
- **Estado**: COMPLETADO Y VERIFICADO.
- **Resultado de pruebas**: 732/732 tests unitarios aprobados (Ran 732 tests in 125.611s - OK).
- **Cumplimiento de politicas**:
  - Regla <= 300 lineas: Cumplida en la totalidad de modulos de `src/procesos_ia/`.
  - Cero emojis: Verificado en todo el proyecto.
  - Botones protegidos: Todos los botones de accion en modales y paneles cuentan con proteccion contra rebotes `ProtectorBotones`.


---

# Fase 5: Refinamiento de DOM y Selectores para Imagenes en DeepSeek y Gemini

- **Objetivo**: Garantizar el pegado exitoso de imagen y la escritura correcta del prompt antes de enviar, evitando envios a ciegas sin imagen.
- **DeepSeek**:
  - Verificacion obligatoria de adjunto de imagen (`ATTACHED_VIA_FILE_INPUT` o `ATTACHED_VIA_PASTE_EVENT`).
  - Solo si el pegado es exitoso (o si no se requeria imagen) se inyecta el prompt mediante el setter React y se dispara el envio.
  - Verificacion de vaciado de textarea y scroll de renderizado.
- **Gemini**:
  - Inyeccion en dos tiempos: pegado de imagen en Base64 con DataTransfer, pausa de 600ms, y asignacion de prompt con InputEvent en el contenteditable.
  - Aceptacion automatica de dialogos de aviso/privacidad de imagen (`upload-image-agree-button`).
  - Deteccion del boton de envio con icono `arrow_upward` y respaldo de Enter.
  - Extraccion blindada de bloques de codigo JSON (`code[data-test-id="code-content"]`) y `model-response`.
