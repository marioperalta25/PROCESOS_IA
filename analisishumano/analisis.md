bien como las reglas ya estan paslamasda en esta misma carpeta vamsoa  crer el plan de sdiseño el patron a aseguri, que es lo que vamos hacer 

## deteccion automatica de ollama
 * aqui vamos hacr la busqueda y la deteccion de programa y eso optimizado super rapido, elegante.
## en caso de que no este instaldo ollama 
 * instalacion autoamtica en segudno plano claramente pridiendo permisos al usario para la isntaalcion y se hace en segundo plano
 *diseño de interfaz y concetividad para que el usario pueda ver todo los mensajes de confirmacion las nevagheaciones y los demas permisso, eso lo vemso en sdiseño de interfaz  
 * notificacion al usuario que ya se instalo 

## deteccion automatica de los mosdelos que esta instalados

* esto la deteccion lo hacemos de la manajera ams rapdia y eficiencie el listado para que el suario pueda elejir que modelo va a usar en las esion que este. 
* rapido, eficiente y coordinado.
## levantamiendo de olla y los modelos
* aqui vine la aprte de analisis de rendimeinto, vamso a analizar cuando el sistema se levante y usar los modelos y garantizar liberar memoria cuando ya no se use 
* importante  la corrida de ollama y los modelos en segundo palno para que trabajen siempre  que haya trbajos largos y pesados.
* falback anti bloqueo  eviatar que los proceso se caigan hacer varias condiciones para los tipos de erores, erorres de conexion, perdida de puerto, etc.
* el usario si quiere apagar los proceso y este amrtia los procesos en segudno palno eso como un btn en la interfaz para que el usario tenga control sobre eso.
* optimizacion de memorias y recursos, los trabajos pesandos lo hace python organizacion de archivos, manejos de archivos, pasarlee data al modelo, todo lo ahce python y el modelo hace las evaluciones, le entrega a python y python hace los concatenaciones o el trabajao que se vaya hacer.
## arquitectura de entrada al modelo y entrada al sistema 
* vamos a los siguienytes modulos
 - integracion de modulo de manejo de archivo aqui incuye 
    * manejo de csv, manejo de xlsx, manejo de txt.
    * arquitectura de abirir archivos de procesarlo csv, utf8, latin etc, no dalñar los archivos de salida,e ntregar formatos validdos para excel separados por comas .
    * el sistema debe de detectar encabezados autoamticamne, y la linea vacioa que le pone excel, analizar si hay encabezado o no, aqui manejo de memoria, ller solo las primeras 5 filas para esa deteccion si no se nota un patron notificacion en tiempo real para el usario para decirle si esa es los encabezados o no.
    el sistema habre la ventanida de windows para seleccion de archivos, y este debe  de estar configurado para abir txt csv y xlsx, asi que tambien logica de capturar los archivos para no darlar los oroiginales.
    * logica y algoritmo iseñado para que la informacion nucna se cruce, jamas ni la que va a dar el modelo, para agregar en lcaso que se quiera agregar alguna calificacion en la misma fila se agrega exatamente en al amisma fila jamas y nuca se debe de combinar o curzarle con la fila de abajo.
    * logica avanzada para  el manejo de archivos de millones de registros, aqui entramos evalucion el rendimeinto de memoria ram, la escritura y lectura en el disco.
    * los arhivos que se procese de donde se extraigan no se tocan, se agarra como una copia, manejo avanzado de esos puntos riticos para no saturar memoria.
    * en la interfaz pedirle al usario que donde quiere guardar los archivos, hacerle una segerencia de gaursar en deskpto osea el escritorio apra ello vamos hacer una logica para leer las ritas y el sistema crea una carpeat base  ahi y donde ira guardadno los arhcivo y tener memoria de que ahi es donde se guardan.
  - modulo  para el manejo de las rutas y deteccion automatica y creacion de acaptea y guardado de archivos: 
   * el sistema debe de contar con logicas de diseño de que lso archivos que se procesen deben de ir en un alamnmiento determiando que es la que el suario elija.  los archios procesado estaran segmentado por carpwtas nombre del archoiv mas fecha la carpeta y ahi el archivo
     - nota si el archivo que se agarra es uno de eso que ya esta en la careta de almacemaiento no se debe de cerear uno nuevo sino que se trabaja sobre el mismo, ya que puede ser que el proceso no se ha completado, o falto algo.
  - modulo de memoria, aqui viene la aprte de si un proceso se pasuo o algo hubo un problema el archivo se guarda en la carpeta determida en su salida, el sistema guarda el registro donde quedo asi cuando el uario vuelva a correr el sistema debra continuar donde quedo y no procesrlo todo.
  - control declicos si la luz se va o la computadora se apaga o pasa algo si trbajamos solo en memroaia ram entonces perdelmos casi todo el proceso debemos de diseñar que el sistema guarde en el disco por lotes  pequeños para que guarde en el disco los progresos y libere la ram, asi no la saturamso pero tambien debemos de diseñar algoritmo para no saturar las lecturas y escrituras del disco.
 - modulo de creacion de pront el usario va a tener un imput donde va a darle clic a una opcion crear promt, aqui es donde entramos nosotros a nicvel de proogramacion.
   * el sistema debe de concetarse con un modleo e inyectar un prommt que tenga por defecto quie crearemso para recrear promt, es decir para este modulo el usario escibe lo que quiere hacer nostros encendemoslo ollama mandamos a llamar el modelo que este libre si no hay un libre ver la menra de conoc onectarlo sin afectar el proceso que corre en caso que corra o bien decirle al usario que no hay modleos disponibles para la rfinacion dle promt.
   * que hara el usario dice quiero hacer esto esto y esto con lal cosa quiero el modelo haga esto y esto con la data que le paasare y listo  entocnes nostros a nivel interno tenemos promt que son base que son para la refinacion de promt entrada por el uario y todo esos promt que el usario vaya creado los guardamso en la isma caprte aqui entra el gestor de ruta, para guardar los promt en archivos.md asi el usario va a querer usar el promt que queira.
 - aqui un punto que no toque en el manejo de archivo es la logica de que es lo que se va hacer con ese archivo, ejemplo bucar palabras en espanol, en x determianda columna, bucar categoria o actiividades que realaliza  + si habla espanol etc, depende que quiera hgacer el usario el sistema al reconcoer si el archivo toiene encabezado le va a preguntar que quiere hacer etc con ee archivo, aqui pas a laparte de la selccion de l promt el sistema debe de reconcocer que siya se selcciono un promt entonces ya entra a la parte que columans columas quiere procesa, la couman que se le va a amndar al modelo, bien aqui un punto importante si le mandamos por lote o no ver el diseño y ver el tipo de respuesta esto lo diseñamos a nivel interno el usario no sabra nada de eso solo nosotros pero si le daremos opciones al usario si procesar por lote o uno por uno y hacerlar el paso, es decir analicearemso als rspuesta y el procesamiento de la memoria integrada y como el llm va a reponder ya que depende de los recursos, tambien vamos a analizar la parte tambien la calibracion de la temperatura del modelo para ser preciso, y todo lo demas que tenga que ver con al respuesta dle modelo, ademas que todo lo que se vaya agregar a los archivos se agrega al fianl de las ultimas columans que tiene todo normalizado menos las url ni anda de eso, en caso que hayan cosas raras.
  * entramos en la parte de como le mandamos los lotes al llm, como gestionamios la respuesta como python va a poner los encabezados para las respuesta de la is, para le manejo de idios, categorias, etc, elñsistema debe ser compelto, con las codiciones para que sea eficiente y con todas las condiciones para que el suario tenfga el control sobre lo que hace y qyue tenga las coas claras
 - diseñamos la parte de las notificonaciones los anuncion o todo lo demas para que el suario simrpe tenga contropl sobre como van los procesos, qaqui diseñamos algun algoritmo de tablero apra que pueda ver como van los progresos en tiempo real, que se ha ehcho y este table no debe de superpar nunca los 10 mg  asi que es importante eso.
 - control absoluto en el usario.
 aqui debemos ver mas que otros modulos necesitamso creo que me hacen falta unos 8 modulos ams para la eficiencia. 

## Modulos complementarios para maxima eficiencia y robustez

1. **Lector por Flujos (Streaming Reader)**:
   - Lectura de archivos gigantescos (millones de registros) mediante generadores e iteradores por bloques (`chunks`).
   - Evita cargar el archivo entero en la memoria RAM, manteniendo el consumo bajo y estable sin importar el tamano del archivo.

2. **Escritor Atomico y Registro WAL con Checkpoints Confirmados**:
   - La recuperacion del proceso debe partir estrictamente del **ultimo progreso confirmado**, nunca de la ultima fila enviada al modelo.
   - Resuelve los dos casos criticos de falla: (a) resultado generado por el modelo pero no confirmado en disco, y (b) resultado persistido en disco pero con puntero de progreso aun no actualizado.
   - El mecanismo WAL (inspirado en el estandar de SQLite) maneja bitacora de cambios, transacciones con confirmacion explicita (`commit`) y checkpoints periodicos de consolidacion.

3. **Normalizador y Sanitizador Estructural de Celdas**:
   - Limpiar celdas por si solo no evita cruces de filas. Un archivo CSV puede contener saltos de linea legitimos dentro de campos entrecomillados segun RFC 4180.
   - Orden estricto de ejecucion: primero se interpreta la estructura tabular formalmente mediante el parser correspondiente; despues se normaliza el contenido de cada celda (escapando comillas huerfanas o caracteres de control).

4. **Evaluador de Capacidad y Contexto (Profiler de Hardware)**:
   - Analisis dinamico y puntual de la memoria RAM y VRAM disponible antes de iniciar la corrida.
   - Ajuste automatico o sugerido del tamano de ventana de contexto (`num_ctx`) y tamano de lote optimo para no sobrecargar la grafica integrada ni el sistema.

5. **Cola Asincrona con Backoff y Cancelacion Cooperativa**:
   - Desacople completo entre la interfaz de usuario y las peticiones al motor de Ollama.
   - Manejo de reintentos exponenciales si el servicio esta saturado y senales de cancelacion inmediata y limpia a peticion del usuario.

6. **Validador de Formato y Evaluacion Semantica del LLM**:
   - Distincion clara entre formato sintactico y validez de negocio: un JSON sintacticamente correcto aun puede contener clasificaciones inexistentes o datos erroneos.
   - Validacion en dos capas:
     * Capa sintactica: Esquema estructurado de Ollama (JSON Schema o modo JSON).
     * Capa semantica/negocio: Validacion de identificador devuelto, completitud de campos, pertenencia a categorias permitidas y deteccion de registros faltantes o duplicados.

7. **Repositorio y Catalogo Local de Prompts (.md)**:
   - Sistema de persistencia y versionado para guardar, clasificar y recuperar los prompts creados y refinados por el usuario.
   - Permite reutilizar estrategias de inferencia comprobadas sin tener que redactarlas de nuevo.

8. **Monitor de Presion de Recursos (< 10 MB)**:
   - Hilo ligero de telemetria con muestreo periodico (1 Hz) del uso de memoria y estado del procesamiento.
   - No almacena historiales pesados en memoria; descarta datos antiguos para cumplir estrictamente el limite de no superar los 10 MB de consumo de RAM.

## Politica de exportacion y particionado de archivos masivos
- Una hoja de Excel admite un limite fisico estricto de 1.048.576 filas (especificacion oficial de Microsoft Excel).
- Procesar volumenes mayores exige una politica de exportacion clara:
  * Segmentacion automatica de salidas en volumenes particionados (ej. `archivo_parte1.xlsx`, `archivo_parte2.xlsx`) al alcanzar 1.000.000 de filas.
  * Opcion de exportacion continua en CSV delimitado por comas sin limite de filas para procesadores de grandes volumenes de datos.

## Coordinador del trabajo y de la identidad de los registros
- **Responsabilidad central**: Conectar el lector de flujos, el asignador de identidad, la cola de inferencia, la validacion y el escritor WAL.
- **Identidad estable de registro**: A cada fila leída se le asigna un identificador inmutable (ID de secuencia o hash de origen). Las respuestas del LLM **nunca se emparejan por posicion ordinal dentro de un lote**, sino mediante este identificador correlacionado.
- **Ciclo de confirmacion**: El coordinador solo avanza el puntero de estado cuando el resultado ha sido validado sintactica y semanticamente, y persistido de manera confirmada en el WAL.

# diseño de interfaz
 * todo los btn deben de estar bien conceta do  
 * los atmjeroa concetados
 * las superxciones en tiempo real conceta bajo rendimeinto de recuros 
 * ui bonita nada de los colores tipicos e  la ia.
 * todo lso btn de control necesario concetados.
 * iconos diseñados especialmente para el sistema  algo asi queiro como un dragon chino, rodeando un circulo como el sol pero que el brillo no lo pierda pro el sol el dragon sino que se vea tipo centra pero eficiente, tambien al fondo  como un universo escondifgo con algunas estrellitas y en una esquina quiero al firma de 
 Frank pero asi como sutil media culta pero que se note, eso para el icnono pricnipal y tambien apra lo de antero jeje.
 
