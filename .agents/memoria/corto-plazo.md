# Estado breve

Actualización: 23 de octubre de 2026. Memoria fijada y estimación por modelo.

## Encargo y resultado

Completada la autorización de añadir Recordar a los mensajes, ajustar el presupuesto
con varias mediciones del modelo y solicitar respuestas concisas para preguntas sencillas.
Se mantiene una generación por envío, streaming, cuota y modelo fijo por conversación.

## Implementación

- PanelMensajes emite identidad y selección literal (o mensaje completo). MemoriaChat
  comprueba su pertenencia y guarda mediante ServicioConversacion.guardar_memoria,
  reutilizado por el editor manual. Sin inferencia adicional ni extracción semántica.
- Los recuerdos se atribuyen al usuario o al modelo. Se evita duplicar el mismo texto.
  Se respetan cuota, versión y bloqueo; durante una inferencia no se puede recordar.
- Los textos extensos abren el editor existente para abreviar. EditorTextoExpandible
  y QScrollArea permiten ampliarlo; Guardar/Cancelar quedan fuera del desplazamiento.
- EstimadorContexto conserva solo números en RAM por modelo/contexto, con caché acotada.
  Espera tres muestras válidas, mantiene margen y relaja gradualmente. El catálogo
  invalida la caché; resultados anteriores no la repueblan. Reaprende al reiniciar.
- Cada petición usa un factor estable. ultima_inferencia registra el factor utilizado
  y los contadores existentes. No se modificó ningún historial real del usuario.
- Instrucción de concisión declarativa en recursos/configuracion/chat.toml; sin
  aumentar num_ctx, reducir el límite de salida, instalar dependencias o cargar modelos.

## Verificación

- Batería completa: 215 pruebas aprobadas en 59.278 s, fuera del sandbox por sockets
  locales de asyncio. Tras fijar el pie del editor: 34 pruebas de interfaz/regresión
  aprobadas en 63.366 s. Los casos enfocados de memoria/estimación también pasaron.
- Sintaxis y máximo de 300 líneas comprobados en 127 archivos Python; TOML válidos.
- Renderizado sintético a 125/150/200 %, anchos de 240 a 1000 y editor compacto:
  sin solapamientos, controles de memoria visibles y altura expandible con scroll.
- No se midió inferencia real, velocidad, RAM o aceleración GPU en este incremento.

## Límites y otros incrementos


- Falta medir latencia, RAM/GPU y tokenización con el modelo real. Los tokens de
  contexto son una estimación; no se promete aceleración ni caché garantizada.
- Cancelar no interrumpe inmediatamente una lectura bloqueada; espera datos o timeout.
- La centralización de salidas en EnrutadorSalidas procede del incremento anterior;
  no se alteró en este encargo. Existen cambios de otros módulos que deben conservarse.
- Las pruebas usan TEMP/TMP dentro de temp/ (ignorado por Git); el temporal redirigido
  del sandbox de Windows impidió crear el bloqueo de archivos en el primer intento.
