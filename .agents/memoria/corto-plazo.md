# Estado breve

Actualizacion: 12 de noviembre de 2026. Reanudacion tabular desde el archivo original implementada.

## Encargo vigente

Seleccionar el archivo original debe localizar la copia de progreso compatible y
continuar pendientes sin perder resultados. El usuario autorizo implementar los
ajustes preservando los flujos existentes. No se promete garantia absoluta frente
a fallos fisicos o comportamiento de servicios externos.

## Implementacion

- `aplicacion/comun/identidad_tabular.py`: vincula origen, contenido, modulo,
  instrucciones, columnas y opciones; no persiste el prompt en sus metadatos.
- `aplicacion/comun/trabajo_tabular.py`: copia completa canonica, confirmacion
  atomica por lote, estados por fila, recuperacion y exportacion independiente.
- `infraestructura/persistencia/bloqueo_trabajo.py`: exclusion de escritores;
  el sistema libera el bloqueo tras un cierre brusco.
- `GestorReanudacionTabular.preparar_trabajo` busca metadatos en las carpetas de
  estado. Los metadatos se mueven junto con el trabajo, sin indices con rutas viejas.
- Modo IA, Gemini, DeepSeek y Lens tabular reciben el contexto opcional del trabajo
  desde sus vistas e hilos. La interfaz no reserva ni mueve salidas al decidir.
- `estado` geografico ya no es progreso. IDs internos estables; resultados del
  modelo se correlacionan por fila; IDs invalidos o repetidos no confirman otras filas.
- Un fallo de disco no se oculta como cancelacion. Puede recuperarse la exportacion
  sin reenviar filas a la IA. Los errores transitorios no marcan como fallida una
  ejecucion posteriormente completada; se eliminan campos de error obsoletos.
- Avances antiguos de Modo IA requieren coincidencia verificable de auditoria y
  registros; los demas se conservan sin reutilizarlos automaticamente.
- Se preservaron los cambios previos del usuario, incluidos los de vistas y salidas.
- Parametros y mensajes nuevos: `recursos/configuracion/salidas.toml`.
- Documentacion: `documentacion/reanudacion-tabular.md`.

## Verificacion

- Bateria ampliada: 129 pruebas aprobadas, con motores simulados y Qt fuera de pantalla.
- Dos regresiones adicionales; las 52 pruebas del grupo afectado se repitieron y
  aprobaron tras la correccion final. Total: 131 casos distintos comprobados.
- Incluye recuperacion desde el original, cancelacion, cierre brusco de un proceso,
  bloqueo de escritores, aislamiento de plantilla/origen, corrupcion, disco y exportacion.
- Deteccion anterior contrastada por lectura de datos y auditoria, sin modificarlos.
- Sintaxis y diferencias del alcance comprobadas. Archivos editados <= 300 lineas.
  Existe un archivo previo de DOM DeepSeek de 340 lineas, ajeno al cambio.
- No se ejecutaron consultas contra motores reales ni se modificaron los datos originales.
- Comando reproducible: `python -B pruebas/ejecutar_reanudacion.py`.
  En el entorno aislado de Windows asyncio no logra abrir su socket interno;
  las pruebas se ejecutaron con escalacion autorizada y dependencias externas simuladas.

## Empaquetado verificado

Compilacion separada completada con PyInstaller 6.19 y Python 3.14:
`dist/reanudacion_validada/PROCESOS_IA/PROCESOS_IA.exe`.
No reemplaza la distribucion anterior. Se verificaron 10 modulos de reanudacion
extraidos del PYZ contra el codigo fuente probado: sus objetos de codigo coinciden.
La configuracion `salidas.toml` incluida coincide byte por byte con el recurso fuente.
La carpeta contiene un LEEME y debe conservar `_internal` junto al ejecutable.
La validacion con navegadores y servicios reales no se ha ejecutado; las pruebas
usaron simulaciones. El progreso se busca bajo la raiz de salida configurada.
