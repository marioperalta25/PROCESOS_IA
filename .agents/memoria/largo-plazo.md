# Índice duradero

Revisión: 23 de octubre de 2026.
La fecha de revisión aplica a las entradas de esta tabla.
Guardar referencias estables; no duplicar reglas ni convertir esta nota en permisos.

| Identificador | Conocimiento | Fuente y estado | Revisar cuando |
| --- | --- | --- | --- |
| M-01 | Idea central: Python, escritorio y Ollama | [D-01](../proyecto/decisiones.md#d-01-python-y-escritorio-modular), confirmado por solicitud inicial | El usuario cambie el objetivo |
| M-02 | Reglas comunes y preferencias de desarrollo | [AGENTS.md](../reglas/AGENTS.md), fuente normativa del proyecto | Cambien reglas o instrucciones del usuario |
| M-03 | El camino del producto sigue por definir | [Estado de las propuestas](../proyecto/decisiones.md#estado-de-las-propuestas), corrección explícita del usuario | Se apruebe una decisión concreta |
| M-04 | Instrucciones neutrales y memoria verificable | [D-06](../proyecto/decisiones.md#d-06-instrucciones-para-distintos-llm), solicitud del 21 de octubre de 2026 | Se evalúe o modifique el esquema |
| M-05 | Modelo fijo desde el primer envío; otro modelo requiere conversación nueva sin contexto heredado | [Chat local](../proyecto/chat-local.md#modelo-fijo-por-conversación), confirmado por el usuario el 22 de octubre de 2026 | El usuario cambie esta política |
| M-06 | Chat rápido: una generación por envío, memoria breve manual y turnos completos recientes; respuesta progresiva | [Chat local](../proyecto/chat-local.md#memoria-y-almacenamiento), autorizado por el usuario el 23 de octubre de 2026 | Cambie la política de contexto o haya medidas reales de latencia |
| M-07 | Recordar texto elegido reutiliza la memoria del chat; calibración acotada por modelo/contexto sin otra inferencia | [Información fijada](../proyecto/chat-local.md#información-fijada-y-estimación), autorizado por el usuario el 23 de octubre de 2026 | Cambie la política de memoria o las mediciones contradigan los márgenes |

La implementación y sus pruebas vigentes son evidencia del comportamiento real.
Las especificaciones vigentes distinguen implementación comprobada y mediciones pendientes.
