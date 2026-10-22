# Ruta de trabajo

Estado: secuencia sugerida anteriormente por el asistente, no aprobada por el usuario.
Las etapas siguientes no autorizan comenzar trabajo ni sustituyen su definición
del producto. El encargo vigente se consulta en la conversación y el estado breve.

## Etapa 0. Cimientos

Entrega: reglas comunes, habilidades especializadas, parámetros declarativos,
arquitectura y dirección visual. Cierre: enlaces válidos, instrucciones coherentes
y habilidades sin contenido de plantilla pendiente.

No incluye aplicación, instalaciones, descargas ni diagnóstico del equipo.

## Etapa 1. Diagnóstico y decisiones verificadas

Consultar de manera puntual Python, Ollama, GPU, controladores y memoria.
Separar lo instalado de lo que está ejecutándose. Verificar la documentación
oficial aplicable antes de elegir dependencias y modelo inicial.

Cierre: compatibilidad conocida o incertidumbre documentada, estrategia de CPU
cuando corresponda y versiones propuestas con sus motivos. Una carga real requiere
un modelo disponible o la elección del usuario antes de su descarga.

## Etapa 2. Esqueleto ejecutable

Crear entorno aislado, manifiesto de dependencias, punto de entrada y composición.
Implementar configuración validada y una primera ventana basada en el diseño.
Incorporar comprobación automatizada del límite de líneas al existir código fuente.

Cierre: apertura y cierre limpios, imports sin operaciones externas, escalado
correcto y arranque sin instalación ni carga de modelos.

## Etapa 3. Conexión con Ollama

Implementar el adaptador y casos de uso para disponibilidad y modelos instalados.
Agregar estados de conexión, tiempos límite y diagnóstico explícito.

Cierre: distinguir servicio detenido, instalación ausente y conexión fallida;
mantener la interfaz disponible durante la consulta.

## Etapa 4. Instalación y dependencias bajo control

Implementar planificación y ejecución de operaciones autorizadas en segundo plano.
Incluir salida legible, cancelación según capacidades reales y verificación final.

Cierre: una instalación previa se reutiliza, una operación fallida no se marca como
exitosa y volver a abrir la aplicación no repite instalaciones o actualizaciones.

## Etapa 5. Primera conversación local

Permitir seleccionar un modelo disponible, enviar una solicitud, recibir respuesta
progresiva y cancelar. Ofrecer descarga de modelos como operación explícita.

Cierre: experiencia fluida, límites de concurrencia y memoria documentados,
errores recuperables y estado real del uso de CPU o GPU cuando pueda verificarse.

## Etapa 6. Rendimiento y crecimiento

Comparar mediciones equivalentes, ajustar políticas de recursos y preparar
distribución cuando el flujo principal sea estable. Agregar capacidades con
contratos pequeños y reutilización de servicios existentes.

Cierre de cada incremento: evidencia del resultado, comprobaciones pertinentes
y registro de decisiones que cambien el comportamiento o las dependencias.
