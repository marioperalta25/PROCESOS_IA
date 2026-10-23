# Conversación local integrada

Fecha: 23 de octubre de 2026.
Estado: implementada en Python/PySide6; pendiente de validación con Ollama real.
El usuario autorizó la integración después de cambiar la navegación a una misma pantalla.

## Acceso y navegación

Conversación en el encabezado abre una VistaChat reutilizable dentro de pila_vistas.
No crea otra ventana ni usa un navegador. Volver conserva el estado. En modo compacto,
Historial sustituye el panel de conversación; seleccionar un chat vuelve al contenido.
Nombre, memoria y confirmación de borrado se editan en la misma vista.

HTML, CSS y JavaScript permanecen únicamente como prototipo de diseño inicial:
[prototipo](../../recursos/diseno/chat-local/index.html) y
[plano SVG](../../recursos/diseno/chat-local/plano.svg). No se importan desde Python.

## Implementación y responsabilidades

| Archivo | Responsabilidad |
| --- | --- |
| [contratos](../../src/procesos_ia/aplicacion/contratos_chat.py) | Repositorio y generador inyectables, sin Qt |
| [conversación](../../src/procesos_ia/aplicacion/conversacion.py) | Contexto reciente, memoria manual, estados y reintento |
| [estimador](../../src/procesos_ia/aplicacion/estimador_contexto.py) | Calibración numérica por modelo/contexto con caché acotada |
| [memoria visual](../../src/procesos_ia/interfaz/chat_memoria.py) | Recordar texto elegido y reutilizar el editor existente |
| [repositorio](../../src/procesos_ia/infraestructura/persistencia/repositorio_chat.py) | Cuota, identidad, archivos atómicos y bloqueo entre escritores |
| [adaptador](../../src/procesos_ia/infraestructura/ollama/chat.py) | Contrato /api/chat, fragmentos y métricas numéricas |
| [transporte](../../src/procesos_ia/infraestructura/ollama/transporte.py) | HTTP compartido y exclusión de inferencias |
| [navegación](../../src/procesos_ia/interfaz/navegacion.py) | Composición diferida, selección y adaptación |
| [vista](../../src/procesos_ia/interfaz/vista_chat.py) | Historial, borradores y acciones del usuario |
| [composición](../../src/procesos_ia/interfaz/chat_composicion.py) | Widgets y distribución nativa |
| [hilo](../../src/procesos_ia/interfaz/chat_hilo.py) | Petición en segundo plano y cancelación cooperativa |
| [progreso](../../src/procesos_ia/interfaz/chat_progreso.py) | Estado visual efímero y fragmentos aislados por conversación |
| [burbujas](../../src/procesos_ia/interfaz/mensajes_chat.py) | Texto seleccionable y distribución por autor |
| [selector](../../src/procesos_ia/interfaz/selector_modelo_chat.py) | Elección para chats nuevos y bloqueo al iniciar |
| [preparador](../../src/procesos_ia/infraestructura/ollama/preparador_chat.py) | Capacidades y límite declarado de contexto en caché acotada |

Los parámetros activos están en
[recursos/configuracion/chat.toml](../../recursos/configuracion/chat.toml).
El archivo [chat-propuesto.toml](../configuracion/chat-propuesto.toml) conserva
la referencia inicial y no es leído por la aplicación.

## Memoria y almacenamiento

- Todas las conversaciones persistidas suman como máximo 10 000 000 bytes lógicos.
  La cuenta incluye archivos gestionados, bloqueo y temporales de reemplazo.
  No equivale al consumo total de RAM de Python, Qt u Ollama ni a bloques del disco.
- Hasta 100 conversaciones, archivos de hasta 1 MiB y lectura de una conversación
  acotada a la vez. La lista retiene títulos, identidad y actividad. Se muestran
  los últimos 40 mensajes; el resto permanece almacenado.
- Este incremento usa JSON por conversación, con UUID en el nombre físico.
  No implementa todavía el JSONL paginado planteado en el diseño inicial.
- Los archivos van al directorio local de datos de la aplicación obtenido mediante
  QStandardPaths, dentro de conversaciones; nunca a .agents ni al repositorio.
- Borradores efímeros: 16 KiB por entrada y 1 MiB agregado. Los borradores sin enviar
  siguen accesibles en la lista temporal; se pierden al cerrar la aplicación.
- Título inicial del primer mensaje y renombrado manual, sin otra inferencia para titular.
- Cada envío realiza una sola generación: instrucción estable, memoria manual de ese
  chat si cabe, turnos completos recientes en orden y mensaje actual. No se resumen
  conversaciones automáticamente ni se inyectan otros chats o memorias de agentes.
- Memoria breve mediante el editor existente. Su presupuesto inicial es de 192 tokens
  estimados, incluido el prefijo. Se reutiliza sin recalcular. Los resúmenes antiguos
  demasiado grandes se conservan: se omiten de la petición y se avisa para abreviarlos.
- El contexto retira los turnos completos más antiguos cuando hace falta y avisa.
  No ofrece memoria literal de intercambios excluidos. Abrir un chat solo lee datos;
  Ollama recibe contexto al enviar el siguiente mensaje.
- Estimación configurable por bytes UTF-8 por token y separación por mensaje, con
  reservas de respuesta y protocolo. No equivale al tokenizador real ni garantiza
  ausencia de truncamiento en todos los modelos e idiomas; no aumenta num_ctx.
- ultima_inferencia conserva solo contadores y tiempos disponibles, además de la
  estimación, el factor utilizado y los indicadores de recorte/memoria. Sin copiar textos a registros
  técnicos. Los campos opcionales ausentes en Ollama se dejan ausentes.
- El usuario elige el modelo en cada chat nuevo. Contexto y temperatura iniciales
  se capturan al primer envío. Se conserva el keep_alive configurable existente.

## Información fijada y estimación

La acción Recordar aparece en mensajes completos. Guarda el fragmento seleccionado
o el mensaje completo mediante ServicioConversacion.guardar_memoria, reutilizado
también por el editor manual. No interpreta semánticamente ni extrae datos con otra
inferencia. Conserva el origen Usuario/Modelo para no presentar automáticamente
una respuesta del modelo como una afirmación del usuario.

La memoria se guarda solo en ese chat y puede editarse o vaciarse. Recordar de nuevo
el mismo texto no añade otra copia. Durante una respuesta, los botones se deshabilitan.
Se comprueban pertenencia del mensaje, fragmento literal, cuota y versión del historial.
Si el contenido supera el presupuesto, se abre el editor expandible para abreviarlo;
no se trunca ni se guarda silenciosamente. Guardar y Cancelar permanecen fuera del
área desplazable. No hay ventanas emergentes.

EstimadorContexto usa una caché en RAM por nombre de modelo y tamaño de contexto.
No recorre historiales al arrancar. Aprende únicamente de respuestas normales
confirmadas con prompt_eval_count válido y un tamaño mínimo de entrada. Al inicio
usa la estimación declarativa; espera tres muestras antes de ajustarla. Conserva
hasta ocho por perfil y aplica margen, límites y cambios graduales al relajar la
estimación. Las muestras más densas aumentan la prudencia sin esperar otro ciclo.

La caché no contiene textos y tiene un máximo configurable de perfiles. Reiniciar
la aplicación o actualizar el catálogo la descarta; una respuesta de una versión
anterior no repuebla una caché invalidada. Cada petición prepara el contexto con
un factor estable. No se mezclan mediciones entre modelos o contextos distintos.
La instrucción del chat solicita concisión para preguntas sencillas y permite detalle
cuando se pide o resulta necesario. No reduce el límite de respuesta ni aumenta num_ctx.

La calibración es empírica: no sustituye al tokenizador y no garantiza exactitud en
todos los idiomas o entradas. No hay medición nueva de velocidad o GPU con modelos
reales en este incremento. La memoria fijada se incluye cuando cabe, con el aviso
existente si queda fuera; guardar un dato no garantiza que cualquier LLM lo utilice bien.

## Durabilidad y concurrencia

Antes de inferir se comprueba espacio para entrada, respuesta y resumen máximos,
incluido escape JSON y pico de reemplazo atómico. El bloqueo de archivos permanece
adquirido durante esa petición: otras instancias pueden leer, pero no ocupar la reserva,
renombrar ni borrar mientras está activa. Si no hay espacio, no se ejecuta el modelo.

Se guarda primero el usuario pendiente; la respuesta se confirma con flush/fsync y
os.replace. Un fallo conserva el último archivo confirmado y permite reintentar
el mismo mensaje sin duplicarlo. Un cierre inesperado puede dejar un pendiente;
no se presenta como éxito. Los temporales no confirmados se limpian bajo bloqueo.
No se borran ni recortan conversaciones automáticamente al alcanzar el límite.

La respuesta queda ligada al chat de origen aunque cambie la vista seleccionada.
No se resucita un chat borrado desde una copia obsoleta. El guardado manual comprueba
la versión conocida para evitar sobrescribir cambios de otra instancia.

El cliente compartido excluye peticiones de inferencia o descarga de modelo simultáneas.
La navegación impide iniciar chat con lote/muestra/refinamiento/descarga activos y
bloquea el refinamiento desde el catálogo si ya hay inferencia. No existe cola diferida.

## Ollama y cierre

Se reutiliza ClienteHttpOllama y su transporte compartido para POST /api/chat,
messages con role/content. La ventana usa stream=true: líneas NDJSON acotadas y
texto plano en message.content, sin format, tools ni adjuntos. Se mantiene el modo
completo para consumidores sin callback. No hay reintentos de una generación progresiva.
Abrir chat no instala, descarga modelos ni arranca servicios.

El trabajador agrupa actualizaciones con un intervalo configurable. La recepción
visual usa QObject/Slot y conexión encolada al hilo de interfaz. Se actualiza el
cuerpo de la burbuja en curso sin reconstruir el historial con cada fragmento.
Los fragmentos son efímeros; solo se confirma la respuesta al recibir done=true
y validar su tamaño. Un corte deja el usuario pendiente para reintentar.

Detener solicita cancelación cooperativa. Se cierra la respuesta HTTP cuando el
lector observa la cancelación; una lectura bloqueada todavía puede esperar su
timeout. No se promete detener inmediatamente la inferencia del servidor. La
interfaz sigue atendiendo eventos y el cierre espera al trabajador.

Referencias: [API de chat](https://docs.ollama.com/api/chat),
[NDJSON](https://docs.ollama.com/api/streaming) y
[afinidad de hilos de Qt](https://doc.qt.io/qtforpython-6/tutorials/basictutorial/signals_and_slots.html#thread-affinity).

El cierre principal espera todos los QThread descendientes, incluidos los de las
subvistas. No usa terminate(). El cierre tolera trabajadores ya eliminados por Qt.
También se aplica el modo de pantalla al activar cada vista y se restablece la
intención de volver al terminar muestras/refinamientos.

Fuentes oficiales: [Ollama chat](https://docs.ollama.com/api/chat).

## Modelo fijo por conversación

Decisión confirmada por el usuario el 22 de octubre de 2026: elegir modelo solo
antes del primer envío. Para utilizar otro, crear una conversación nueva y vacía,
sin transferir historial ni resumen. No se implementa cambio de modelo en chats iniciados.

El catálogo y su consulta existente se reutilizan dentro del chat. Elegir un modelo
no lo carga ni genera texto. Actualizar modelos es una acción explícita y puede
invocar el arranque local ya autorizado por ese control, sin instalar ni descargar.

El primer mensaje pendiente guarda el modelo del chat y los parámetros efectivos.
El modelo sigue fijo después de errores, cancelaciones y reinicios; las respuestas
nuevas registran su procedencia. Aplicación y repositorio rechazan sustituirlo.
Los historiales anteriores sin modelo registrado son legibles, renombrables y
borrables, pero requieren otra conversación para continuar: no se inventa su origen.
Si el modelo desaparece del catálogo, se conserva su nombre y el borrador.

Se consulta /api/show desde el trabajador antes de inferir. La caché retiene solo
capacidad de texto y contexto declarado, con un máximo configurable de modelos;
se invalida al actualizar el catálogo. No conserva licencias, plantillas ni vocabularios.
Si el contexto elegido supera un máximo declarado válido, se reduce y se informa
el valor efectivo. La ausencia de metadatos en versiones antiguas no permite afirmar
un límite desconocido. Esto no demuestra RAM disponible ni aceleración por GPU.

Los mensajes del usuario aparecen a la derecha en verde suave y las respuestas a
la izquierda en arena, con etiquetas de autor/modelo además del color. Se mantiene
texto plano seleccionable y ajuste incluso sin espacios, sin interpretar HTML.
Las burbujas muestran la ventana acotada de mensajes existente y no cargan el
historial completo. Cambiar el tamaño adapta ancho y distribución.

## Verificación y pendientes

Pruebas de cuota UTF-8, fallo de reemplazo, reintentos, cancelación, aislamiento,
memoria manual, versión obsoleta, exclusión entre escritores, límite HTTP, navegación,
borradores, teclado y cierre. Resultados actuales en la memoria breve.
Renderizado fuera de pantalla revisado a 700 x 600, 750 x 650 y 1040 x 780.
Datos de las capturas y respuestas de pruebas son sintéticos.

Pendientes: petición con Ollama/modelo real, medición de RAM/GPU/latencia,
comprobación visual en el escritorio real. Escalas 125/150/200 % verificadas únicamente mediante renderizado aislado, sin confirmar escalado real de Windows.
No se afirma límite de 10 MB para toda la aplicación en RAM.
