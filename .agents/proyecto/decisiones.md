# Decisiones y pendientes

Fecha de preparación: 21 de octubre de 2026.

## Estado de las propuestas

El usuario aclaró en esta conversación que solo se había definido la idea central
y las reglas, y que el camino del producto todavía no estaba plasmado. PySide6,
Qt Widgets, la paleta y el orden de etapas fueron sugerencias del asistente.
Conservarlas como propuestas; no usarlas como requisitos ni decisiones aprobadas.

## D-01. Python y escritorio modular

Estado: acordado por la solicitud inicial.
Interfaz y coordinación en Python, capas explícitas y Ollama como servicio externo.
Las reglas comunes se mantienen en `AGENTS.md`; las habilidades contienen los
procedimientos específicos y `proyecto.toml` los parámetros declarativos iniciales.

## D-02. Biblioteca de interfaz

Estado: propuesta, pendiente de prototipo y compatibilidad.
PySide6 con Qt Widgets permite trabajar con componentes de escritorio desde Python
y soporte de alta densidad. Es una base para conseguir nitidez y un lenguaje visual
propio; el resultado depende también de estilos, recursos y pruebas de escalado.

Antes de instalar: verificar versiones compatibles de Python y PySide6, requisitos
de distribución y licencia. No fijar versiones sin esa comprobación.

Fuentes oficiales:
- [Qt para Python](https://doc.qt.io/qtforpython-6/).
- [Alta densidad en Qt](https://doc.qt.io/qtforpython-6/overviews/qtdoc-highdpi.html).

## D-03. Ollama y gráfica integrada

Estado: objetivo acordado; compatibilidad del equipo pendiente.
El usuario indica que Ollama ya está instalado. No se ha comprobado su versión,
su estado ni el hardware del equipo durante esta etapa.

La documentación de Ollama distingue soporte por hardware, sistema y backend.
No dar por hecho que cualquier gráfica integrada puede acelerar cualquier modelo.
Consultar la documentación vigente al implementar; no copiar ajustes experimentales
o variables de entorno sin comprobar su necesidad y su alcance.

Diagnóstico futuro: identificar GPU exacta, controladores, memoria disponible,
versión de Ollama y ejecución real de una carga pequeña autorizada. Si la GPU
no puede utilizarse, informar el motivo conocido o la incertidumbre y ofrecer
operación en CPU con un modelo adecuado al equipo.

Fuente: [soporte oficial de hardware de Ollama](https://docs.ollama.com/gpu).

## D-04. Recursos y arranque

Estado: acordado por la solicitud inicial.
Arranque ligero, operaciones bajo demanda y caché pequeña con invalidación
explícita. Sin tareas periódicas de instalación ni diagnósticos completos al abrir.
Una generación simultánea como punto de partida; ajustar con mediciones reales.
Los límites de memoria y contexto se definirán después del diagnóstico.

La cifra de una generación simultánea es propuesta del asistente, no una elección
confirmada del usuario. Los parámetros operativos siguen pendientes de definición.

## D-05. Instalación asistida

Estado: funcionalidad futura, no implementada.
Separar detección, planificación, ejecución y verificación. El usuario controla
el plan y ve progreso y resultados. La aplicación no modifica controladores,
servicios ni privilegios como consecuencia silenciosa de un error de conexión.

## Datos por resolver en la siguiente etapa

| Dato | Cómo resolverlo |
| --- | --- |
| GPU integrada y controladores | Consulta puntual del sistema |
| Memoria disponible y presión de uso | Medición durante diagnóstico y carga representativa |
| Versión y disponibilidad de Ollama | Consulta local acotada |
| Python y biblioteca gráfica compatibles | Revisión oficial y prueba aislada |
| Primer modelo, tamaño y cuantización | Elegir después del diagnóstico |
| Presupuestos de rendimiento | Medir arranque, latencia y consumo antes de fijarlos |

Actualizar este registro cuando exista evidencia nueva, conservando el motivo de
las decisiones que afecten contratos, dependencias o experiencia del usuario.

## D-06. Instrucciones para distintos LLM

Estado: solicitado por el usuario el 21 de octubre de 2026 en esta conversación.
Fuente: petición de análisis oficial y reglas claras, impacto antes de editar,
eficiencia de contexto y memoria de corto y largo plazo para distintos modelos.

Alcance: instrucciones y habilidades para desarrollo. No autoriza implementar
la aplicación ni elegir su biblioteca de interfaz, modelos o secuencia de funciones.
El esquema concreto es una implementación revisable de esa petición; su eficacia
entre herramientas requiere evaluación. Revisar cuando cambie el encargo o haya
evidencia de fallos, crecimiento de contexto o incompatibilidad de integración.

## D-07. Carpeta única para agentes

Estado: solicitado por el usuario el 22 de octubre de 2026 en esta conversación.
Fuente: petición de reunir el material para LLM en una carpeta dividida por secciones.
Alcance: organización documental, conservando reglas y habilidades. La ubicación
elegida es .agents; AGENTS.md y README.md permanecen como entradas breves en la raíz.
Revisar si el usuario cambia el orden o una integración necesita adaptar su entrada.
