---
name: interfaz-escritorio
description: Diseñar o implementar pantallas, componentes y estados de la aplicación de escritorio PROCESOS_IA en Python. Aplicar a interacción, estilo, accesibilidad y escalado.
---

# Interfaz de escritorio

Leer [las reglas comunes](../../reglas/AGENTS.md). Confirmar en
[el registro técnico](../../proyecto/decisiones.md) si existe una biblioteca
elegida. [El diseño](../../proyecto/diseno-interfaz.md) es una propuesta;
consultarlo cuando corresponda sin asumir que el usuario aprobó sus valores.

## Procedimiento

1. Confirmar la pantalla y el flujo de la etapa actual. Buscar componentes,
   estilos y presentadores reutilizables antes de crear otros.
2. Diseñar estados vacío, ocupado, completado, cancelado y fallido para ese flujo.
   Indicar qué puede hacer el usuario en cada uno.
3. Reutilizar los valores visuales existentes y aprobados. Si el encargo autoriza
   proponer diseño, distinguir propuesta de decisión; mantener los valores elegidos
   en un único recurso del tema, sin imponer la paleta sugerida anteriormente.
4. Conectar acciones a casos de uso inyectados. El código visual no conoce comandos
   de instalación ni URLs de endpoints específicos de Ollama.
5. Ejecutar trabajo lento fuera del hilo de interfaz y transferir resultados mediante
   mecanismos seguros del framework elegido. Si se adopta Qt, modificar widgets
   solo desde su hilo principal; no dar esa elección por hecha.
6. Comprobar teclado, foco, contraste, escalado y textos largos antes de entregar.

## Criterios específicos

- Utilizar layouts adaptables; evitar fijar posiciones de todos los elementos.
- Cargar recursos locales nítidos y componentes funcionales sin decoración excesiva.
- Mantener la acción principal visible y los detalles técnicos accesibles al necesitarlos.
- No mostrar porcentajes inventados; usar progreso indeterminado cuando no se mida.
- Una cancelación solicitada se diferencia de una tarea ya cancelada.
- Presentar errores con causa conocida y siguiente acción, sin volcar trazas al usuario.
- Revisar callbacks, señales y datos de presentación al cambiar contratos consumidos.
- No volver a solicitar autorización si el mismo plan ya cuenta con una válida.

## Resultado verificable

La pantalla permanece utilizable durante tareas lentas, respeta la dirección visual
y se puede recorrer con teclado. Informar qué escalas se verificaron realmente;
documentar las pendientes sin afirmar que fueron probadas.
