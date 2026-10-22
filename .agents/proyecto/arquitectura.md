# Arquitectura inicial

Estado: propuesta anterior del asistente, pendiente de definición por el usuario.
Consultar como antecedente; este documento no fija el camino del producto.

## Dirección

Aplicación de escritorio modular dentro de un único proceso de Python, con Ollama
como servicio externo. Modularidad no exige microservicios: los límites de código
y los contratos permiten crecer sin multiplicar procesos o infraestructura.

La estructura siguiente es una propuesta para la implementación futura; sus
carpetas se crearán al incorporar una responsabilidad real.

```text
src/procesos_ia/
    arranque/           Punto de entrada, composición y cierre
    dominio/           Entidades, valores y reglas sin dependencias externas
    aplicacion/        Casos de uso, contratos y coordinación
    infraestructura/   Adaptadores concretos
        ollama/        Servicio HTTP y traducción de respuestas
        sistema/       Procesos, instalación y diagnóstico del equipo
        persistencia/  Preferencias, estado y caché local
    presentacion/      Ventanas, componentes y estado visual
    recursos/          Estilos, iconos vectoriales y recursos visuales
pruebas/
    unitarias/
    integracion/
```

## Dependencias permitidas

| Capa | Puede conocer | No debe conocer |
| --- | --- | --- |
| Dominio | Biblioteca estándar y conceptos propios | Qt, HTTP, comandos, archivos del sistema |
| Aplicación | Dominio y contratos propios | Widgets, clientes concretos, instaladores concretos |
| Infraestructura | Contratos de aplicación y dominio | Ventanas o componentes de presentación |
| Presentación | Casos de uso y datos de presentación | Comandos, detalles HTTP o instalación |
| Arranque | Implementaciones necesarias para conectarlas | Reglas de negocio nuevas |

Los contratos pertenecen a aplicación; infraestructura los implementa. Arranque
conecta implementaciones sin introducir un localizador global de servicios.
Los casos de uso devuelven resultados o eventos; no muestran cuadros de diálogo.
La presentación transforma esas salidas en estados comprensibles para el usuario.

## Instancias únicas y ciclo de vida

Interpretación del requisito de singleton: una instancia compartida por aplicación
para recursos que deban conservar identidad, no una clase singleton para todo.

| Recurso futuro | Alcance propuesto | Cierre |
| --- | --- | --- |
| Configuración validada | Una instancia preferiblemente inmutable | Sin tareas activas |
| Cliente de Ollama | Un cliente compartido, según seguridad de concurrencia | Cerrar conexiones |
| Coordinador de tareas | Una instancia con cola y límites | Cancelar y esperar con límite |
| Repositorio de preferencias | Una instancia | Confirmar escritura y liberar recursos |
| Ventanas y datos de cada solicitud | Instancias según su uso | Liberar al terminar |

Construir estos recursos en composición e inyectarlos. Las pruebas pueden crear
contenedores independientes; no deben reiniciar estado global para funcionar.
No compartir una conexión o cliente entre hilos si su biblioteca no lo permite.

## Arranque ligero

1. Cargar preferencias locales pequeñas y valores predeterminados validados.
2. Crear la interfaz y los recursos livianos necesarios.
3. Consultar la disponibilidad de Ollama bajo demanda, con un tiempo límite.
4. Usar diagnóstico completo solo por acción explícita o necesidad justificada.

La ausencia de Ollama muestra un estado recuperable y acceso al módulo de
instalación. No dispara reparación, descarga ni actualización automática.
Un fallo de conexión no demuestra que Ollama no esté instalado: distinguir
ausencia del ejecutable, servicio detenido y servicio inaccesible.

## Operaciones largas

La presentación solicita tareas; aplicación las coordina mediante contratos.
Infraestructura usa procesos o comunicación asíncrona según el trabajo real.
Qt recibe resultados mediante mecanismos seguros para su hilo principal.

Cada tarea tiene identidad, estado, progreso cuando sea medible, cancelación y
resultado. Los estados de instalación no deben mezclarse con los de generación.
El cierre de la aplicación detiene únicamente recursos y procesos que le pertenecen;
no mata una instancia de Ollama iniciada previamente por el usuario.

## Crecimiento

Añadir módulos por capacidades existentes, con contratos pequeños. Reutilizar
servicios mediante inyección; evitar carpetas genéricas que acumulen lógica
como `utilidades` o `gestor_general`. Un cambio de estructura debe conservar
los consumidores o migrarlos de manera verificable.
