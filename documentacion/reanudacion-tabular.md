# Reanudacion desde el archivo original

El usuario selecciona el archivo original y conserva el proceso, las columnas y las
instrucciones que desea aplicar. La aplicacion identifica el trabajo compatible y
ofrece continuar pendientes, recuperar fallos, reiniciar otra ejecucion o recuperar
el archivo de resultados cuando no quedan filas por consultar.

## Persistencia y contratos

- `TrabajoTabular` es propietario de la copia de progreso de una ejecucion. Las
  vistas preparan la decision; el hilo reserva o retoma la salida y escribe.
- La identidad vincula ruta original, datos, modulo, instrucciones, columnas y
  opciones de hoja o imagen. No se guarda el prompt dentro de los metadatos.
- `trabajo_tabular.json` acompana a la carpeta al pasar entre los estados de
  `EnrutadorSalidas`; asi la ubicacion del respaldo no depende de una ruta obsoleta.
- `progreso_tabular.csv` contiene una fila por registro original desde el inicio.
  Usa `_id_registro`, `_estado_ia`, `_motivo_estado` y `_fecha_procesamiento`.
- Cada lote se combina por ID y se confirma mediante el escritor atomico existente
  con `flush`, `fsync` y reemplazo del archivo. El avance visible se actualiza
  despues de escribir. Se guarda el CSV completo una vez por lote confirmado,
  ademas de la inicializacion. No se promete escritura de costo constante por lote.
- El CSV de salida se exporta al finalizar o cancelar. Puede desglosar telefonos;
  esa expansion no cambia el numero de registros del progreso canonico.
- Un bloqueo del sistema operativo evita escritores simultaneos para la misma
  identidad. Se libera tambien cuando el proceso termina inesperadamente.
- Cambios del origen o del progreso entre la decision y la ejecucion detienen el
  trabajo. Un respaldo faltante, truncado o con metadatos invalidos produce error.
- Una excepcion de persistencia no se oculta como cancelacion. Los lotes anteriores
  confirmados permanecen recuperables. La exportacion puede repetirse sin IA.

## Compatibilidad

Modo IA, Gemini, DeepSeek y Lens tabular usan esta misma copia. Las firmas anteriores
conservan sus argumentos posicionales; se agrega `trabajo_tabular` como parametro
opcional. La continuacion de una salida escrita exige el contexto verificado; una
salida existente sin ese contexto no se sobrescribe.

Las carpetas de imagenes y el escritor WAL local mantienen sus contratos. El cursor
secuencial del WAL no se reutiliza como sustituto de los estados por fila.

Un avance antiguo de Modo IA sin identidad solo se incorpora automaticamente si su
auditoria coincide en instrucciones y datos enviados, y sus filas corresponden al
original. El nombre del archivo no basta. Los respaldos antiguos sin esa evidencia
se conservan y no se reutilizan automaticamente. No se migran datos al arrancar.

## Verificacion reproducible

Ejecutar desde la raiz con las dependencias del proyecto:

```powershell
python -B pruebas/ejecutar_reanudacion.py
```

Las pruebas sustituyen los motores por simulaciones. Cubren seleccion del original,
cancelacion, recuperacion, cierre brusco de un proceso, bloqueo de escritores,
respuesta parcial, errores de escritura, cambio de plantilla y exportacion. En
Windows, `asyncio` necesita que el entorno permita su socket local interno.

La confirmacion es por lote: una solicitud enviada cuya respuesta aun no se haya
guardado puede repetirse al recuperar el trabajo. La durabilidad frente a fallos
fisicos del almacenamiento depende tambien del sistema operativo y del dispositivo.
La validacion de los navegadores y servicios reales se realiza por separado.

## Evidencia del 12 de noviembre de 2026

- Bateria ampliada: 129 pruebas aprobadas, incluidas rutas, conexiones, imagenes y WAL local.
- Se agregaron dos regresiones sobre errores transitorios y recuperacion de envios.
  Las 52 pruebas de los consumidores afectados se repitieron y aprobaron despues
  de esa correccion. Son 131 casos distintos comprobados en total.
- La revision de sintaxis y diferencias no detecto errores en el alcance editado;
  los archivos de codigo del cambio no superan 300 lineas.
- La deteccion del respaldo anterior se verifico tambien mediante una lectura
  del origen y su auditoria, sin modificar ni procesar los datos reales.
- Se genero una distribucion separada en `dist/reanudacion_validada/PROCESOS_IA`.
  Se verificaron los modulos de reanudacion del PYZ contra el codigo fuente probado
  y la copia de `salidas.toml` incluida en sus recursos.
